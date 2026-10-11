"""Mezcla el trafico benigno de tu navegador con el campus emulado.

El ataque no sale del contenedor. Docker publica el puerto solo en
127.0.0.1; un proxy TCP de este proceso abre las conexiones hacia el
portal con BENIGN_CLIENT_IP. Esa IP no es un alumno ni una PC infectada,
asi que la etiqueta sigue siendo BENIGN.

Al cerrar la captura se parte el pcap en tres carpetas:

    data/analisis/<escenario>/benigno/
    data/analisis/<escenario>/ataque/
    data/analisis/<escenario>/compartido/
"""
import csv
import os
import re
import shutil
import socket
import subprocess
import threading

from paths import analysis_dir
from roles import (
    BENIGN_CLIENT_IP,
    BENIGN_CLIENT_NAME,
    BENIGN_IFACE,
    BENIGN_PEER,
    VICTIM_IP,
    VICTIM_NAME,
    bots,
    students,
)

_LINE = re.compile(
    r'length (\d+): (\d+\.\d+\.\d+\.\d+)(?:\.\d+)? > (\d+\.\d+\.\d+\.\d+)'
)
_proxy = {'stop': None, 'sock': None}


def benign_port():
    raw = os.environ.get('BENIGN_PORT', '')
    try:
        port = int(raw) if raw else 8080
    except ValueError:
        port = 8080
    if port < 1 or port > 65535:
        return 8080
    return port


def benign_url():
    return 'http://127.0.0.1:%d/' % benign_port()


def _run(args):
    return subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _offload_off(iface):
    ethtool = '/usr/sbin/ethtool' if os.path.isfile('/usr/sbin/ethtool') else 'ethtool'
    _run([
        ethtool, '-K', iface,
        'tx', 'off', 'rx', 'off', 'tso', 'off', 'gso', 'off', 'gro', 'off',
    ])


def stop_benign():
    stop = _proxy.get('stop')
    sock = _proxy.get('sock')
    if stop is not None:
        stop.set()
    if sock is not None:
        try:
            sock.close()
        except OSError:
            pass
    _proxy['stop'] = None
    _proxy['sock'] = None
    _run(['ovs-vsctl', '--if-exists', 'del-port', BENIGN_PEER])
    _run(['ip', 'link', 'del', BENIGN_IFACE])


def _pipe(src, dst):
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            dst.sendall(data)
    except OSError:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except OSError:
            pass


def _handle(client, victim):
    remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        remote.bind((BENIGN_CLIENT_IP, 0))
        remote.settimeout(5)
        remote.connect((victim, 80))
        remote.settimeout(None)
    except OSError:
        client.close()
        remote.close()
        return
    left = threading.Thread(target=_pipe, args=(client, remote), daemon=True)
    right = threading.Thread(target=_pipe, args=(remote, client), daemon=True)
    left.start()
    right.start()
    left.join()
    right.join()
    client.close()
    remote.close()


def _serve(sock, stop, victim):
    while not stop.is_set():
        try:
            client, _addr = sock.accept()
        except socket.timeout:
            continue
        except OSError:
            break
        threading.Thread(target=_handle, args=(client, victim), daemon=True).start()


def start_proxy(victim):
    if _proxy['sock'] is not None:
        return
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('0.0.0.0', benign_port()))
    sock.listen(128)
    sock.settimeout(1.0)
    stop = threading.Event()
    threading.Thread(target=_serve, args=(sock, stop, victim), daemon=True).start()
    _proxy['stop'] = stop
    _proxy['sock'] = sock


def attach_benign_client(switch, victim=VICTIM_IP):
    """Cuelga una puerta del contenedor en el switch DMZ y abre el proxy.

    Devuelve (ok, mensaje). Si falla, el escenario sigue sin tu navegador.
    """
    stop_benign()
    try:
        subprocess.check_call([
            'ip', 'link', 'add', BENIGN_IFACE, 'type', 'veth', 'peer', 'name', BENIGN_PEER,
        ])
        subprocess.check_call(['ip', 'link', 'set', BENIGN_IFACE, 'up'])
        subprocess.check_call(['ip', 'link', 'set', BENIGN_PEER, 'up'])
        subprocess.check_call(['ip', 'addr', 'add', '%s/8' % BENIGN_CLIENT_IP, 'dev', BENIGN_IFACE])
        _offload_off(BENIGN_IFACE)
        _offload_off(BENIGN_PEER)
        for key in ('all', BENIGN_IFACE):
            _run(['sysctl', '-w', 'net.ipv4.conf.%s.rp_filter=0' % key])
        subprocess.check_call(['ovs-vsctl', 'add-port', switch.name, BENIGN_PEER])
        start_proxy(victim)
    except (OSError, subprocess.CalledProcessError) as exc:
        stop_benign()
        return False, str(exc)
    return True, benign_url()


def iface_counter(iface, name):
    path = '/sys/class/net/%s/statistics/%s' % (iface, name)
    try:
        with open(path) as fh:
            return int(fh.read().strip())
    except (OSError, ValueError):
        return None


def _role(ip, scenario, student_ips, bot_ips):
    if ip == VICTIM_IP:
        return 'portal'
    if ip == BENIGN_CLIENT_IP:
        return 'benigno_real'
    if ip in bot_ips:
        if scenario == 'baseline':
            return 'benigno'
        return 'ataque'
    if ip in student_ips:
        return 'benigno'
    return 'otro'


def _names():
    found = {ip: name for name, ip in list(students()) + list(bots())}
    found[BENIGN_CLIENT_IP] = BENIGN_CLIENT_NAME
    found[VICTIM_IP] = VICTIM_NAME
    return found


def _read_packets(pcap_path):
    if not os.path.isfile(pcap_path) or os.path.getsize(pcap_path) == 0:
        return []
    proc = subprocess.run(
        ['tcpdump', '-nn', '-e', '-r', pcap_path],
        capture_output=True, text=True, errors='replace',
    )
    rows = []
    for line in (proc.stdout or '').splitlines():
        match = _LINE.search(line)
        if not match:
            continue
        rows.append((match.group(2), match.group(3), int(match.group(1))))
    return rows


def _write_slice(src_pcap, dst_pcap, ips):
    if not ips or not os.path.isfile(src_pcap):
        open(dst_pcap, 'wb').close()
        return
    bpf = ' or '.join('host %s' % ip for ip in ips)
    subprocess.run(
        ['tcpdump', '-r', src_pcap, '-w', dst_pcap, bpf],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _pct(part, whole):
    if not whole:
        return ''
    return '%.1f' % (100.0 * part / whole)


def split_capture(pcap_path, meta, metrics_path=None):
    """Parte la captura y escribe el reparto benigno / ataque."""
    scenario = (meta or {}).get('scenario') or 'escenario'
    root = analysis_dir(scenario)
    benign_dir = os.path.join(root, 'benigno')
    attack_dir = os.path.join(root, 'ataque')
    share_dir = os.path.join(root, 'compartido')
    for path in (benign_dir, attack_dir, share_dir):
        os.makedirs(path, exist_ok=True)

    student_ips = list((meta or {}).get('students') or [])
    bot_ips = list((meta or {}).get('bots') or [])
    benign_ips = list(student_ips) + [BENIGN_CLIENT_IP]
    attack_ips = []
    if scenario == 'baseline':
        benign_ips.extend(bot_ips)
    else:
        attack_ips = list(bot_ips)

    _write_slice(pcap_path, os.path.join(benign_dir, 'trafico.pcap'), benign_ips)
    _write_slice(pcap_path, os.path.join(attack_dir, 'trafico.pcap'), attack_ips)

    if metrics_path and os.path.isfile(metrics_path):
        shutil.copyfile(metrics_path, os.path.join(share_dir, 'sonda.csv'))
    meta_path = os.path.splitext(pcap_path)[0] + '.meta.json'
    if os.path.isfile(meta_path):
        shutil.copyfile(meta_path, os.path.join(share_dir, 'meta.json'))

    names = _names()
    packets = {}
    nbytes = {}
    for src, _dst, length in _read_packets(pcap_path):
        packets[src] = packets.get(src, 0) + 1
        nbytes[src] = nbytes.get(src, 0) + length

    client_pkts = 0
    client_bytes = 0
    for ip, count in packets.items():
        role = _role(ip, scenario, set(student_ips), set(bot_ips))
        if role in ('benigno', 'benigno_real', 'ataque'):
            client_pkts += count
            client_bytes += nbytes.get(ip, 0)

    ip_rows = []
    for ip in sorted(packets, key=lambda item: (-packets[item], item)):
        role = _role(ip, scenario, set(student_ips), set(bot_ips))
        share_pkts = ''
        share_bytes = ''
        if role in ('benigno', 'benigno_real', 'ataque'):
            share_pkts = _pct(packets[ip], client_pkts)
            share_bytes = _pct(nbytes[ip], client_bytes)
        ip_rows.append({
            'ip': ip,
            'nombre': names.get(ip, ''),
            'rol': role,
            'paquetes': packets[ip],
            'bytes': nbytes[ip],
            'pct_paquetes_clientes': share_pkts,
            'pct_bytes_clientes': share_bytes,
        })

    by_role = {}
    for row in ip_rows:
        slot = by_role.setdefault(row['rol'], {'paquetes': 0, 'bytes': 0})
        slot['paquetes'] += row['paquetes']
        slot['bytes'] += row['bytes']

    role_order = ('benigno_real', 'benigno', 'ataque', 'portal', 'otro')
    role_rows = []
    for role in role_order:
        slot = by_role.get(role)
        if not slot:
            continue
        role_rows.append({
            'rol': role,
            'paquetes': slot['paquetes'],
            'bytes': slot['bytes'],
            'pct_paquetes_clientes': _pct(slot['paquetes'], client_pkts) if role != 'portal' else '',
            'pct_bytes_clientes': _pct(slot['bytes'], client_bytes) if role != 'portal' else '',
        })

    ip_header = [
        'ip', 'nombre', 'rol', 'paquetes', 'bytes',
        'pct_paquetes_clientes', 'pct_bytes_clientes',
    ]
    role_header = [
        'rol', 'paquetes', 'bytes', 'pct_paquetes_clientes', 'pct_bytes_clientes',
    ]
    with open(os.path.join(share_dir, 'por_ip.csv'), 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=ip_header)
        writer.writeheader()
        writer.writerows(ip_rows)
    with open(os.path.join(share_dir, 'reparto.csv'), 'w', newline='') as fh:
        writer = csv.DictWriter(fh, fieldnames=role_header)
        writer.writeheader()
        writer.writerows(role_rows)

    def _count(role, key):
        return by_role.get(role, {}).get(key, 0)

    lines = [
        'Escenario: %s' % scenario,
        'Portal: %s' % VICTIM_IP,
        'Tu navegador entra como %s (%s).' % (BENIGN_CLIENT_IP, benign_url()),
        'Los pcap de benigno/ y ataque/ incluyen la respuesta del portal a ese grupo.',
        'Los porcentajes cuentan solo quien envia (no las respuestas del portal).',
        '',
        'Paquetes de clientes: %d' % client_pkts,
        '  benigno_real (tu navegador): %s%%' % (_pct(_count('benigno_real', 'paquetes'), client_pkts) or '0.0'),
        '  benigno (alumnos): %s%%' % (_pct(_count('benigno', 'paquetes'), client_pkts) or '0.0'),
        '  ataque: %s%%' % (_pct(_count('ataque', 'paquetes'), client_pkts) or '0.0'),
        'Respuestas del portal: %d paquetes' % _count('portal', 'paquetes'),
    ]
    if _count('benigno_real', 'paquetes') == 0:
        lines.append('No llego trafico de tu navegador. Abre %s mientras la medicion corre.' % benign_url())
    text_path = os.path.join(share_dir, 'reparto.txt')
    with open(text_path, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    return root, '\n'.join(lines)
