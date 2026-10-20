#!/usr/bin/env python3
"""Controlador Ryu que ademas de reenviar, recolecta estadisticas de flujo.

simple_switch_13 solo aprende MACs y reenvia: no mira el trafico. Esta
version hace lo mismo para que la red siga funcionando, pero agrega dos
cosas que son las que aportan la "vista SDN" al dataset:

1. Instala los flujos de IPv4 emparejando por (ipv4_src, ipv4_dst,
   ip_proto). Asi cada entrada de la tabla de flujos corresponde a un par
   de IPs y su protocolo, y sus contadores (paquetes, bytes, duracion) se
   pueden etiquetar por la IP que los genero.

2. Un hilo pide cada SDN_POLL_INTERVAL segundos las estadisticas de flujo
   a cada switch (FlowStatsRequest) y las escribe en SDN_FLOWS_CSV. Esa es
   la telemetria que luego pcap_to_csv.py cruza con las conexiones.

No instala flujos por puerto L4 a proposito: en Open vSwitch userspace
(Docker/WSL) una tabla con un flujo por paquete de un flood tumba el
emulador. Un flujo por par de IPs es estable y basta para medir ritmos.

Corre dentro del venv de Ryu:
    SDN_FLOWS_CSV=/ataque/data/metrics/baseline_sdn.csv \
    ryu-manager /ataque/mininet/flow_monitor_13.py --ofp-tcp-listen-port 6653
"""
import csv
import os
import time

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import ether_types, ethernet, packet
from ryu.ofproto import ofproto_v1_3


CSV_FIELDS = [
    'timestamp', 'dpid', 'src_ip', 'dst_ip', 'proto', 'packets', 'bytes',
    'duration_s',
]


def _csv_path():
    return os.environ.get('SDN_FLOWS_CSV', '/ataque/data/metrics/sdn_flows.csv')


def _poll_interval():
    raw = os.environ.get('SDN_POLL_INTERVAL', '2')
    try:
        value = float(raw)
    except ValueError:
        return 2.0
    return value if value > 0 else 2.0


class FlowMonitor13(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(FlowMonitor13, self).__init__(*args, **kwargs)
        self.mac_to_port = {}
        self.datapaths = {}
        self.csv_path = _csv_path()
        self.poll_interval = _poll_interval()
        self._ensure_csv()
        self.monitor_thread = hub.spawn(self._monitor)

    # ---- escritura del CSV de telemetria -------------------------------

    def _ensure_csv(self):
        folder = os.path.dirname(self.csv_path)
        if folder:
            try:
                os.makedirs(folder, exist_ok=True)
            except OSError:
                pass
        # Reescribe el encabezado en cada corrida: un escenario = un archivo.
        try:
            with open(self.csv_path, 'w', newline='') as fh:
                csv.writer(fh).writerow(CSV_FIELDS)
        except OSError as exc:
            self.logger.warning('No se pudo crear %s: %s', self.csv_path, exc)

    def _append_rows(self, rows):
        if not rows:
            return
        try:
            with open(self.csv_path, 'a', newline='') as fh:
                writer = csv.writer(fh)
                writer.writerows(rows)
        except OSError as exc:
            self.logger.warning('No se pudo escribir %s: %s', self.csv_path, exc)

    # ---- hilo de monitoreo ---------------------------------------------

    def _monitor(self):
        while True:
            for dp in list(self.datapaths.values()):
                self._request_stats(dp)
            hub.sleep(self.poll_interval)

    def _request_stats(self, datapath):
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply(self, ev):
        now = int(time.time())
        dpid = ev.msg.datapath.id
        rows = []
        for stat in ev.msg.body:
            match = stat.match
            src = match.get('ipv4_src')
            dst = match.get('ipv4_dst')
            if src is None or dst is None:
                # table-miss, ARP u otros flujos sin IP: no aportan al dataset.
                continue
            proto = match.get('ip_proto', 0)
            rows.append([
                now, dpid, src, dst, proto, stat.packet_count,
                stat.byte_count, stat.duration_sec,
            ])
        self._append_rows(rows)

    # ---- plano de datos: switch de aprendizaje con flujos por IP -------

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features(self, ev):
        datapath = ev.msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        match = parser.OFPMatch()
        actions = [parser.OFPActionOutput(ofproto.OFPP_CONTROLLER,
                                          ofproto.OFPCML_NO_BUFFER)]
        self._add_flow(datapath, 0, match, actions)

    def _add_flow(self, datapath, priority, match, actions, buffer_id=None):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        kwargs = dict(datapath=datapath, priority=priority, match=match,
                      instructions=inst)
        if buffer_id is not None:
            kwargs['buffer_id'] = buffer_id
        datapath.send_msg(parser.OFPFlowMod(**kwargs))

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        in_port = msg.match['in_port']

        pkt = packet.Packet(msg.data)
        eth = pkt.get_protocols(ethernet.ethernet)[0]
        if eth.ethertype == ether_types.ETH_TYPE_LLDP:
            return

        dst = eth.dst
        src = eth.src
        dpid = datapath.id
        self.mac_to_port.setdefault(dpid, {})
        self.mac_to_port[dpid][src] = in_port

        if dst in self.mac_to_port[dpid]:
            out_port = self.mac_to_port[dpid][dst]
        else:
            out_port = ofproto.OFPP_FLOOD

        actions = [parser.OFPActionOutput(out_port)]

        if out_port != ofproto.OFPP_FLOOD:
            match = self._match_for(parser, in_port, eth, pkt)
            if msg.buffer_id != ofproto.OFP_NO_BUFFER:
                self._add_flow(datapath, 1, match, actions, msg.buffer_id)
                return
            self._add_flow(datapath, 1, match, actions)

        data = None
        if msg.buffer_id == ofproto.OFP_NO_BUFFER:
            data = msg.data
        out = parser.OFPPacketOut(datapath=datapath, buffer_id=msg.buffer_id,
                                  in_port=in_port, actions=actions, data=data)
        datapath.send_msg(out)

    def _match_for(self, parser, in_port, eth, pkt):
        """IPv4 -> flujo por (src, dst, proto); el resto, por MAC."""
        from ryu.lib.packet import ipv4
        ip = pkt.get_protocol(ipv4.ipv4)
        if eth.ethertype == ether_types.ETH_TYPE_IP and ip is not None:
            return parser.OFPMatch(
                eth_type=ether_types.ETH_TYPE_IP,
                ipv4_src=ip.src,
                ipv4_dst=ip.dst,
                ip_proto=ip.proto,
            )
        return parser.OFPMatch(in_port=in_port, eth_dst=eth.dst, eth_src=eth.src)
