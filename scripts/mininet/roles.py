"""Quien es quien en el campus reducido de la UNCP.

Cada switch de facultad es un laboratorio de esa area, no la facultad
entera. Los alumnos y los infectados hablan con el mismo portal.

Las intensidades de ataque, las pausas del navegado y la semilla se leen
del entorno (con los mismos valores por defecto de antes). Asi una tanda
de varias corridas puede variarlas por corrida sin tocar el codigo, y
cada corrida queda registrada en el meta.json.
"""
import os
import random

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


# --------------------------------------------------------------------------
# Perfiles de ataque: ataques MAS DIFICILES de detectar.
#
# Con las intensidades por defecto cada clase se separa con 2-3 umbrales
# (un arbol de profundidad 3 ya da F1 0,995): el modelo aprende los numeros
# del simulador, no la forma del ataque. Un perfil cambia COMO ataca la
# botnet para acercarla al trafico normal:
#
#   normal    lo de siempre (valores fijos por defecto).
#   bajo      intensidad baja: pocos paquetes / conexiones por PC.
#   sigiloso  muy baja, 1 PC infectada por area y HTTP flood que imita la
#             navegacion (paginas al azar, pausas irregulares).
#   pulsos    intensidad normal pero a rafagas: ON unos segundos, OFF otros.
#   rampa     las PCs infectadas se suman de a una a lo largo de RAMP_S
#             segundos: al principio ataca una sola.
#
# Un rango (lo, hi) se sortea con la semilla de la corrida (reproducible).
# Una variable de entorno explicita siempre gana sobre el perfil.
# Los nombres tienen que coincidir con ui/server/catalog.py (PERFILES).
# --------------------------------------------------------------------------
_PPS_ALL = ('SYN_PPS', 'ICMP_PPS', 'UDP_PPS', 'ACK_PPS')
_CONNS_ALL = ('SLOWLORIS_CONNS', 'SLOWPOST_CONNS')

PERFILES = {
    'normal': {},
    'bajo': dict(
        {k: (4, 8) for k in _PPS_ALL},
        **{k: (5, 8) for k in _CONNS_ALL},
        HTTP_FLOOD_WORKERS=(1, 2), HTTP_FLOOD_PAUSE=(0.3, 0.6),
    ),
    'sigiloso': dict(
        {k: (1, 3) for k in _PPS_ALL},
        **{k: (2, 4) for k in _CONNS_ALL},
        HTTP_FLOOD_WORKERS=(1, 1), HTTP_FLOOD_PAUSE=(0.4, 0.9),
        HTTP_FLOOD_MIMIC=1, BOTS_PER_AREA=1,
    ),
    'pulsos': dict(
        ATTACK_MODE='pulsos', PULSE_ON_S=(3, 6), PULSE_OFF_S=(8, 15),
    ),
    'rampa': dict(
        {k: (8, 20) for k in _PPS_ALL},
        **{k: (8, 20) for k in _CONNS_ALL},
        HTTP_FLOOD_WORKERS=(2, 4),
        ATTACK_MODE='rampa', RAMP_S=(40, 60),
    ),
}

ATTACK_PROFILE = os.environ.get('ATTACK_PROFILE', '').strip().lower() or 'normal'
if ATTACK_PROFILE not in PERFILES:
    ATTACK_PROFILE = 'normal'

# Carga benigna: 'fija' (4 alumnos por area, pausas 0,5-1,5 s) o 'variable'
# (se sortea por corrida, tambien en baseline). Con carga variable el trafico
# normal a veces se parece al de un ataque bajo: sin eso los falsos
# positivos salen 0 % siempre y no dicen nada.
BENIGN_LOAD = os.environ.get('BENIGN_LOAD', '').strip().lower() or 'fija'
_BENIGN_VARIABLE = {
    'STUDENTS_PER_AREA': (3, 8),
    'BROWSE_PAUSE_MIN': (0.2, 0.7),
    'BROWSE_PAUSE_SPAN': (0.5, 1.2),
}


def _sorteo(name, spec):
    """Valor de un rango del perfil, fijo para (semilla, perfil, variable)."""
    if not isinstance(spec, tuple):
        return spec
    rng = random.Random('%s:%s:%s:%s' % (RUN_SEED, ATTACK_PROFILE, BENIGN_LOAD, name))
    lo, hi = spec
    if isinstance(lo, int) and isinstance(hi, int):
        return rng.randint(lo, hi)
    return round(rng.uniform(lo, hi), 2)


def _param(name, default, cast):
    """Entorno explicito > perfil (o carga variable) > valor por defecto."""
    raw = os.environ.get(name, '').strip()
    if raw:
        try:
            return cast(float(raw)) if cast is int else cast(raw)
        except ValueError:
            pass
    spec = PERFILES[ATTACK_PROFILE].get(name)
    if spec is None and BENIGN_LOAD == 'variable':
        spec = _BENIGN_VARIABLE.get(name)
    if spec is None:
        return default
    return cast(_sorteo(name, spec))


# Recortados a [1, 9]: los alumnos usan .10+i y las infectadas .20+i, asi que
# ninguno de los dos puede pasar de 9 por area sin invadir el rango del otro.
STUDENTS_PER_AREA = max(1, min(9, _param('STUDENTS_PER_AREA', 4, int)))
BOTS_PER_AREA = max(1, min(9, _param('BOTS_PER_AREA', 2, int)))

BROWSE_PAUSE_MIN = _param('BROWSE_PAUSE_MIN', 0.5, float)
BROWSE_PAUSE_MAX = _param(
    'BROWSE_PAUSE_MAX', round(BROWSE_PAUSE_MIN + _param('BROWSE_PAUSE_SPAN', 1.0, float), 2), float)
HTTP_FLOOD_PAUSE = _param('HTTP_FLOOD_PAUSE', 0.1, float)
HTTP_FLOOD_WORKERS = _param('HTTP_FLOOD_WORKERS', 4, int)
# 1 = el HTTP flood pide paginas al azar con pausas irregulares, como un alumno
# muy activo, en vez de martillar '/' a ritmo fijo.
HTTP_FLOOD_MIMIC = _param('HTTP_FLOOD_MIMIC', 0, int)
SYN_PPS = max(1, _param('SYN_PPS', 20, int))
ICMP_PPS = max(1, _param('ICMP_PPS', 20, int))
SLOWLORIS_CONNS = max(1, _param('SLOWLORIS_CONNS', 20, int))
UDP_PPS = max(1, _param('UDP_PPS', 20, int))
ACK_PPS = max(1, _param('ACK_PPS', 20, int))
SLOWPOST_CONNS = max(1, _param('SLOWPOST_CONNS', 20, int))

# Forma del ataque en el tiempo: 'constante' | 'pulsos' | 'rampa'.
ATTACK_MODE = _param('ATTACK_MODE', 'constante', str).strip().lower()
if ATTACK_MODE not in ('constante', 'pulsos', 'rampa'):
    ATTACK_MODE = 'constante'
PULSE_ON_S = max(1, _param('PULSE_ON_S', 5, int))
PULSE_OFF_S = max(1, _param('PULSE_OFF_S', 10, int))
RAMP_S = max(0, _param('RAMP_S', 45, int))

# Segundo en que arranca el ataque dentro de una corrida de ataque. Antes de
# eso las PCs infectadas navegan igual que los alumnos (todo es BENIGN); a
# partir de ahi atacan. 0 = ataque desde el primer segundo (comportamiento
# anterior). MACHINE_TAG identifica la maquina que genero la corrida.
ONSET_S = _env_int('ONSET_S', 30)
MACHINE_TAG = os.environ.get('MACHINE_TAG', '').strip()


def onset_for(duration):
    """Segundo del ataque para una corrida de `duration` s. Si la corrida es
    corta (pruebas de 20 s) el ataque arranca a un cuarto del tiempo."""
    if ONSET_S <= 0:
        return 0
    if duration >= ONSET_S + 10:
        return ONSET_S
    return max(1, duration // 4)


def run_config():
    """Lo que vario en esta corrida, para guardarlo en el meta.json."""
    return {
        'run_tag': RUN_TAG,
        'seed': RUN_SEED,
        'onset_s': ONSET_S,
        'machine_tag': MACHINE_TAG,
        'browse_pause_min': BROWSE_PAUSE_MIN,
        'browse_pause_max': BROWSE_PAUSE_MAX,
        'http_flood_pause': HTTP_FLOOD_PAUSE,
        'http_flood_workers': HTTP_FLOOD_WORKERS,
        'syn_pps': SYN_PPS,
        'icmp_pps': ICMP_PPS,
        'slowloris_conns': SLOWLORIS_CONNS,
        'udp_pps': UDP_PPS,
        'ack_pps': ACK_PPS,
        'slowpost_conns': SLOWPOST_CONNS,
        'students_per_area': STUDENTS_PER_AREA,
        'bots_per_area': BOTS_PER_AREA,
        'multivector_attacks': list(MULTIVECTOR_ATTACKS),
        'attack_profile': ATTACK_PROFILE,
        'benign_load': BENIGN_LOAD,
        'attack_mode': ATTACK_MODE,
        'pulse_on_s': PULSE_ON_S,
        'pulse_off_s': PULSE_OFF_S,
        'ramp_s': RAMP_S,
        'http_flood_mimic': HTTP_FLOOD_MIMIC,
    }


def ramp_delays(bot_names):
    """Segundo (desde la orden del C2) en que arranca cada PC infectada.
    Constante/pulsos: todas a la vez. Rampa: repartidas en RAMP_S segundos,
    en un orden sorteado con la semilla para que no entren por area."""
    names = list(bot_names)
    if ATTACK_MODE != 'rampa' or len(names) < 2 or RAMP_S <= 0:
        return {n: 0 for n in names}
    order = names[:]
    random.Random('%s:rampa' % RUN_SEED).shuffle(order)
    step = RAMP_S / float(len(order) - 1)
    return {n: int(round(i * step)) for i, n in enumerate(order)}


def tagged(scenario):
    """Nombre de archivo de la corrida: 'synflood' o 'synflood__r03'."""
    return '%s__%s' % (scenario, RUN_TAG) if RUN_TAG else scenario


def _load_scenarios():
    """Lee scripts/mininet/scenarios.txt, el registro unico de escenarios.
    Vive junto a este archivo a proposito: esa carpeta se copia entera a
    /ataque/mininet en la imagen Docker, asi que la misma ruta relativa
    funciona adentro y afuera del contenedor sin distinguir el entorno.

    Devuelve (todos, base): 'base' son los que no llevan la marca 'extra'."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scenarios.txt')
    default = ('baseline', 'synflood', 'httpflood', 'slowloris', 'icmpflood')
    try:
        with open(path) as fh:
            lines = [ln.strip() for ln in fh]
    except OSError:
        return default, default
    todos, base = [], []
    for ln in lines:
        if not ln or ln.startswith('#'):
            continue
        parts = ln.split()
        todos.append(parts[0])
        if 'extra' not in parts[1:]:
            base.append(parts[0])
    return tuple(todos), tuple(base)


SCENARIOS, CORE_SCENARIOS = _load_scenarios()

# Ataques individuales: lo que se puede combinar en 'multivector'.
ATTACKS = tuple(s for s in SCENARIOS if s not in ('baseline', 'multivector'))


def _load_multivector():
    """Ataques que se reparten entre las infectadas en el escenario
    'multivector' (MULTIVECTOR_ATTACKS=synflood,icmpflood,...). Se descartan
    nombres invalidos y repetidos; hacen falta al menos dos, si no se usa el
    valor por defecto."""
    raw = os.environ.get('MULTIVECTOR_ATTACKS', '')
    found = []
    for name in (x.strip() for x in raw.split(',')):
        if name in ATTACKS and name not in found:
            found.append(name)
    if len(found) < 2:
        found = [a for a in ('synflood', 'icmpflood', 'slowloris') if a in ATTACKS]
    return tuple(found)


MULTIVECTOR_ATTACKS = _load_multivector()

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
