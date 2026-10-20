"""Quien es quien en el campus reducido de la UNCP.

Cada switch de facultad es un laboratorio de esa area, no la facultad
entera. Los alumnos y los infectados hablan con el mismo portal.

Las intensidades de ataque, las pausas del navegado y la semilla se leen
del entorno (con los mismos valores por defecto de antes). Asi una tanda
de varias corridas puede variarlas por corrida sin tocar el codigo, y
cada corrida queda registrada en el meta.json.
"""
import os

VICTIM_NAME = 'www'
VICTIM_IP = '10.0.0.10'
MODEM_CAMPUS_IP = '10.0.0.1'
C2_NAME = 'c2'
C2_IP = '192.168.9.10'
C2_GW = '192.168.9.1'

# Tu navegador entra por el proxy del contenedor. Sale hacia el portal
# con esta IP, distinta de alumnos e infectados, y se etiqueta BENIGN.
BENIGN_CLIENT_NAME = 'benigno-real'
BENIGN_CLIENT_IP = '10.9.0.1'
BENIGN_IFACE = 'benign0'
BENIGN_PEER = 'benign1'

# Un laboratorio por area academica de la UNCP (Huancayo).
AREAS = (
    ('salud', '10.1.0', 'Salud'),
    ('ing', '10.2.0', 'Ingenierias y Arquitectura'),
    ('emp', '10.3.0', 'Administracion, Contabilidad y Economia'),
    ('soc', '10.4.0', 'Sociales y Educacion'),
    ('agr', '10.5.0', 'Ciencias Agrarias'),
)

STUDENTS_PER_AREA = 4
BOTS_PER_AREA = 2

# Paginas del portal. Los alumnos no salen a internet: recorren esto.
PAGES = ('/', '/login', '/notas', '/aula', '/biblioteca')

# El portal de prueba es chico a proposito: tarda un poco y tiene pocos
# cupos. Asi 10 PCs infectadas alcanzan para que los alumnos lo noten
# dentro de Docker. Un servidor real de campus no se cae con este ritmo.
PAGE_DELAY_S = 0.4
MAX_CONNECTIONS = 30

def _env_float(name, default):
    try:
        return float(os.environ.get(name, '') or default)
    except ValueError:
        return float(default)


def _env_int(name, default):
    try:
        return int(float(os.environ.get(name, '') or default))
    except ValueError:
        return int(default)


# Etiqueta de corrida (sufijo de los archivos) y semilla registrada. Sin
# RUN_TAG los nombres de archivo quedan como antes (compatibilidad).
RUN_TAG = os.environ.get('RUN_TAG', '').strip()
RUN_SEED = _env_int('RUN_SEED', 0)

BROWSE_PAUSE_MIN = _env_float('BROWSE_PAUSE_MIN', 0.5)
BROWSE_PAUSE_MAX = _env_float('BROWSE_PAUSE_MAX', 1.5)
HTTP_FLOOD_PAUSE = _env_float('HTTP_FLOOD_PAUSE', 0.1)
HTTP_FLOOD_WORKERS = _env_int('HTTP_FLOOD_WORKERS', 4)
SYN_PPS = _env_int('SYN_PPS', 20)
ICMP_PPS = _env_int('ICMP_PPS', 20)
SLOWLORIS_CONNS = _env_int('SLOWLORIS_CONNS', 20)


def run_config():
    """Lo que vario en esta corrida, para guardarlo en el meta.json."""
    return {
        'run_tag': RUN_TAG,
        'seed': RUN_SEED,
        'browse_pause_min': BROWSE_PAUSE_MIN,
        'browse_pause_max': BROWSE_PAUSE_MAX,
        'http_flood_pause': HTTP_FLOOD_PAUSE,
        'http_flood_workers': HTTP_FLOOD_WORKERS,
        'syn_pps': SYN_PPS,
        'icmp_pps': ICMP_PPS,
        'slowloris_conns': SLOWLORIS_CONNS,
    }


def tagged(scenario):
    """Nombre de archivo de la corrida: 'synflood' o 'synflood__r03'."""
    return '%s__%s' % (scenario, RUN_TAG) if RUN_TAG else scenario


SCENARIOS = ('baseline', 'synflood', 'httpflood', 'slowloris', 'icmpflood')

# Mininet solo calcula el dpid si el switch se llama s1, s2, ...
CORE_SWITCH = 's1'
DMZ_SWITCH = 's2'


def area_switch(key):
    keys = [item[0] for item in AREAS]
    return 's%d' % (3 + keys.index(key))


def students():
    """(nombre, ip) de cada PC de alumno."""
    for key, prefix, _title in AREAS:
        for i in range(STUDENTS_PER_AREA):
            yield '%s-u%d' % (key, i + 1), '%s.%d' % (prefix, 10 + i)


def bots():
    """(nombre, ip) de cada PC infectada."""
    for key, prefix, _title in AREAS:
        for i in range(BOTS_PER_AREA):
            yield '%s-b%d' % (key, i + 1), '%s.%d' % (prefix, 20 + i)


def area_of(hostname):
    return hostname.split('-', 1)[0]
