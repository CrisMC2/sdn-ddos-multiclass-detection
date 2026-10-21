#!/usr/bin/env python3
"""Controlador Ryu que ademas de reenviar, recolecta estadisticas de flujo.

simple_switch_13 solo aprende MACs y reenvia: no mira el trafico. Esta
version hace lo mismo para que la red siga funcionando, pero agrega dos
cosas que son las que aportan la "vista SDN" al dataset:

1. Instala los flujos de IPv4 emparejando por (ipv4_src, ipv4_dst,
   ip_proto). Asi cada entrada de la tabla de flujos corresponde a un par
   de IPs y su protocolo, y el trafico se puede etiquetar por la IP que lo
   genero.

2. Un hilo pide cada SDN_POLL_INTERVAL segundos los contadores de flujo y
   los escribe en SDN_FLOWS_CSV. Esa es la telemetria que luego
   pcap_to_csv.py cruza con las conexiones y build_windows.py convierte en
   features por ventana.

   OJO (por que se leen del DATAPATH y no de OpenFlow): pedir las
   estadisticas por OpenFlow (OFPFlowStatsRequest) NO sirve para floods
   sostenidos sin puertos L4. En OVS (userspace y kernel por igual) el
   contador OpenFlow de una regla solo se actualiza cuando el flujo del
   datapath que la implementa se destruye. El TCP crea y destruye muchos
   flujos de datapath (puertos origen variables) asi que su contador
   OpenFlow crece; pero el ICMP es UN solo flujo de datapath que nunca se
   destruye, asi que su contador OpenFlow se congela a los ~5 s aunque el
   trafico siga (se confirmo: el plano de datos y 'ovs-dpctl' crecen toda
   la corrida, solo el contador OpenFlow se pega). Como la telemetria
   alimenta al detector por ventana, eso borraba la senal de icmpflood.
   Por eso aqui los contadores se toman de 'ovs-dpctl dump-flows', que
   refleja el trafico real para todos los protocolos. Se lleva el estado
   por flujo del datapath para reconstruir un acumulado monotono por
   (src, dst, proto) aunque los flujos del datapath aparezcan y desaparezcan.

No instala flujos por puerto L4 a proposito: en Open vSwitch una tabla con
un flujo por paquete de un flood tumba el emulador. Un flujo por par de IPs
es estable y basta para medir ritmos.

Corre dentro del venv de Ryu:
    SDN_FLOWS_CSV=/ataque/data/metrics/baseline_sdn.csv \
    ryu-manager /ataque/mininet/flow_monitor_13.py --ofp-tcp-listen-port 6653
"""
import csv
import os
import re
import subprocess
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

# Un flujo del datapath se parte en "match" (antes de ", packets:") y
# "stats". El match identifica al flujo (lleva in_port + cabeceras) y sirve
# de clave estable para calcular deltas entre muestreos.
_IPV4_RE = re.compile(r'ipv4\(src=([0-9.]+)[^,]*,dst=([0-9.]+)[^,]*,proto=(\d+)')
_PKTS_RE = re.compile(r'packets:(\d+)')
_BYTES_RE = re.compile(r'bytes:(\d+)')


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
        # Estado para reconstruir acumulados monotonos desde el datapath.
        self._dp_prev = {}       # match del flujo de datapath -> (pkts, bytes)
        self._cum = {}           # (src, dst, proto) -> [pkts, bytes]
        self._first_seen = {}    # (src, dst, proto) -> timestamp
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

    # ---- hilo de monitoreo: contadores desde el datapath ---------------

    def _monitor(self):
        while True:
            try:
                self._poll_datapath()
            except Exception as exc:  # nunca matar el hilo por un muestreo
                self.logger.warning('muestreo del datapath fallo: %s', exc)
            hub.sleep(self.poll_interval)

    def _dump_datapath_flows(self):
        """Texto crudo de 'ovs-dpctl dump-flows' (todos los datapaths)."""
        try:
            return subprocess.check_output(
                ['ovs-dpctl', 'dump-flows'],
                stderr=subprocess.DEVNULL, text=True, timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            return ''

    def _poll_datapath(self):
        """Suma los deltas de cada flujo del datapath en un acumulado por
        (src, dst, proto) y escribe una fila por flujo logico en este muestreo.

        Los contadores del datapath solo crecen mientras el flujo vive; al
        morir desaparece pero su ultimo delta ya quedo sumado. Si un match se
        reusa y su contador reinicia (cur < prev), se cuenta como flujo nuevo.
        """
        text = self._dump_datapath_flows()
        if not text:
            return
        now = int(time.time())
        for line in text.splitlines():
            head, sep, tail = line.partition(', packets:')
            if not sep:
                continue
            m = _IPV4_RE.search(head)
            if not m:
                continue  # ARP, LLDP u otros sin IPv4: no aportan al dataset
            src, dst, proto = m.group(1), m.group(2), m.group(3)
            pm = _PKTS_RE.search('packets:' + tail)
            bm = _BYTES_RE.search(tail)
            if not pm:
                continue
            pkts = int(pm.group(1))
            nbytes = int(bm.group(1)) if bm else 0
            prev = self._dp_prev.get(head)
            if prev is None or pkts < prev[0]:
                d_pkts, d_bytes = pkts, nbytes          # flujo nuevo o reiniciado
            else:
                d_pkts, d_bytes = pkts - prev[0], nbytes - prev[1]
            self._dp_prev[head] = (pkts, nbytes)
            key = (src, dst, proto)
            acc = self._cum.get(key)
            if acc is None:
                acc = [0, 0]
                self._cum[key] = acc
                self._first_seen[key] = now
            acc[0] += d_pkts
            acc[1] += max(0, d_bytes)

        rows = []
        for (src, dst, proto), (pkts, nbytes) in self._cum.items():
            dur = max(0.0, now - self._first_seen.get((src, dst, proto), now))
            rows.append([now, 0, src, dst, proto, pkts, nbytes, round(dur, 3)])
        self._append_rows(rows)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            self.datapaths.pop(datapath.id, None)

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
