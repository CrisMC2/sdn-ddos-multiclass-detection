"""Catalogo de escenarios: lo que la interfaz muestra de cada uno.

La lista valida de nombres sigue siendo scenarios.txt; esto es solo como se
presentan. Un escenario que no este aqui se muestra con valores genericos,
asi que agregar uno a scenarios.txt no rompe la UI.

'intensidad' es el unico parametro que se ofrece para ese ataque. Los rangos
son los que se probaron estables en Open vSwitch (el CLAUDE.md avisa que
subirlos a niveles de un ataque real tumba el emulador).

'forma' decide como se dibujan sus paquetes en el campus:
  volumen -> muchos paquetes chicos y rapidos
  app     -> peticiones completas, ritmo medio
  lento   -> pocos paquetes que tardan en llegar y se acumulan

Las frases de 'firma' salen de corridas reales de este banco, no de teoria.
"""
from .config import SCENARIOS_FILE

GRUPOS = ('Referencia', 'Volumen', 'Aplicación', 'Cupos de conexión', 'Combinado')

# Perfiles de ataque (forma de atacar). Los valores reales viven en
# scripts/mininet/roles.py (PERFILES): aqui solo como se presentan. Los ids
# tienen que coincidir con los de roles.py.
PERFILES = (
    {'id': 'normal', 'nombre': 'Normal',
     'descripcion': 'Intensidad fija de siempre. Fácil de detectar: sirve de referencia.'},
    {'id': 'bajo', 'nombre': 'Baja intensidad',
     'descripcion': 'Pocos paquetes o conexiones por PC (sorteados con la semilla). Se acerca al tráfico normal.'},
    {'id': 'sigiloso', 'nombre': 'Sigiloso',
     'descripcion': 'Muy baja intensidad, 1 PC infectada por área y HTTP flood que imita a un alumno (páginas al azar, pausas irregulares).'},
    {'id': 'pulsos', 'nombre': 'A pulsos',
     'descripcion': 'Ataca a ráfagas: unos segundos sí (ON) y varios no (OFF). Las ventanas OFF quedan como BENIGN.'},
    {'id': 'rampa', 'nombre': 'Rampa',
     'descripcion': 'Las PCs infectadas se suman de a una durante 40-60 s: al principio ataca una sola.'},
)
PERFIL_IDS = tuple(p['id'] for p in PERFILES)

CATALOGO = {
    'baseline': {
        'grupo': 'Referencia', 'icono': 'baseline', 'nombre': 'Sin ataque', 'forma': None,
        'descripcion': 'Alumnos e infectadas navegan el portal igual. Es el punto de comparación: todo queda BENIGN.',
        'agota': 'Nada: el portal trabaja en condiciones normales.',
        'firma': 'Paquetes por segundo y latencia estables durante toda la corrida.',
        'herramienta': 'curl',
        'intensidad': None,
    },
    'synflood': {
        'grupo': 'Volumen', 'icono': 'syn', 'nombre': 'SYN flood', 'forma': 'volumen',
        'descripcion': 'Cada infectada manda paquetes SYN que piden abrir conexiones TCP y nunca las completan.',
        'agota': 'La tabla de conexiones a medio abrir y el ancho de banda del portal.',
        'firma': 'La tasa de paquetes al portal es la más alta de todos los ataques; los flujos son de uno o dos paquetes con bandera SYN.',
        'herramienta': 'hping3 -S -p 80',
        'intensidad': {'env': 'SYN_PPS', 'etiqueta': 'Paquetes SYN por segundo, por PC', 'defecto': 20, 'min': 1, 'max': 60},
    },
    'httpflood': {
        'grupo': 'Aplicación', 'icono': 'http', 'nombre': 'HTTP flood', 'forma': 'app',
        'descripcion': 'Las infectadas piden páginas completas sin pausa, con varios procesos a la vez.',
        'agota': 'La capacidad de la aplicación para atender peticiones.',
        'firma': 'La latencia del portal sube. Son peticiones completas, no paquetes sueltos, por eso la tasa de paquetes no es la más alta.',
        'herramienta': 'curl en bucle',
        'intensidad': {'env': 'HTTP_FLOOD_WORKERS', 'etiqueta': 'Procesos simultáneos, por PC', 'defecto': 4, 'min': 1, 'max': 8},
    },
    'slowloris': {
        'grupo': 'Cupos de conexión', 'icono': 'slow', 'nombre': 'Slowloris', 'forma': 'lento',
        'descripcion': 'Abre muchas conexiones y envía las cabeceras HTTP a goteo para que el servidor no las cierre.',
        'agota': 'Los cupos de conexión del portal (30).',
        'firma': 'Pocos paquetes por segundo, pero el portal deja de responder: casi todas las sondas del alumno fallan.',
        'herramienta': 'slowhttptest -H',
        'intensidad': {'env': 'SLOWLORIS_CONNS', 'etiqueta': 'Conexiones abiertas, por PC', 'defecto': 20, 'min': 1, 'max': 40},
    },
    'icmpflood': {
        'grupo': 'Volumen', 'icono': 'icmp', 'nombre': 'ICMP flood', 'forma': 'volumen',
        'descripcion': 'Inundación de ping hacia el portal.',
        'agota': 'El ancho de banda.',
        'firma': 'Tráfico ICMP: en la telemetría SDN, la fracción de paquetes ICMP pasa de cero a más de la mitad.',
        'herramienta': 'ping (kernel)',
        'intensidad': {'env': 'ICMP_PPS', 'etiqueta': 'Pings por segundo, por PC', 'defecto': 20, 'min': 1, 'max': 60},
    },
    'udpflood': {
        'grupo': 'Volumen', 'icono': 'udp', 'nombre': 'UDP flood', 'forma': 'volumen',
        'descripcion': 'Datagramas UDP sin saludo previo; el portal responde «puerto inalcanzable» a cada uno.',
        'agota': 'CPU y ancho de banda.',
        'firma': 'Tráfico UDP: en la telemetría SDN, la fracción de paquetes UDP pasa de cero a más de la mitad.',
        'herramienta': 'hping3 --udp -p 80',
        'intensidad': {'env': 'UDP_PPS', 'etiqueta': 'Datagramas por segundo, por PC', 'defecto': 20, 'min': 1, 'max': 60},
    },
    'ackflood': {
        'grupo': 'Volumen', 'icono': 'ack', 'nombre': 'ACK flood', 'forma': 'volumen',
        'descripcion': 'Paquetes TCP con bandera ACK sin una conexión real detrás; el portal responde RST.',
        'agota': 'La tabla de estado de conexiones y el ancho de banda.',
        'firma': 'Por ventana se parece a un SYN flood: la bandera ACK solo se distingue en los flujos, no en la telemetría SDN.',
        'herramienta': 'hping3 -A -p 80',
        'intensidad': {'env': 'ACK_PPS', 'etiqueta': 'Paquetes ACK por segundo, por PC', 'defecto': 20, 'min': 1, 'max': 60},
    },
    'slowpost': {
        'grupo': 'Cupos de conexión', 'icono': 'post', 'nombre': 'Slow POST (RUDY)', 'forma': 'lento',
        'descripcion': 'Envía un POST a /login que anuncia un cuerpo enorme y lo entrega byte a byte.',
        'agota': 'Los cupos de conexión del portal.',
        'firma': 'Las conexiones abiertas se disparan por encima del cupo y el portal empieza a responder 503.',
        'herramienta': 'slowhttptest -B',
        'intensidad': {'env': 'SLOWPOST_CONNS', 'etiqueta': 'Conexiones abiertas, por PC', 'defecto': 20, 'min': 1, 'max': 40},
    },
    'multivector': {
        'grupo': 'Combinado', 'icono': 'multi', 'nombre': 'Varios a la vez', 'forma': 'mixto',
        'descripcion': 'Cada PC infectada lanza uno de los ataques elegidos, todos al mismo tiempo contra el mismo portal.',
        'agota': 'Depende de la mezcla: puede combinar presión de ancho de banda con agotamiento de cupos.',
        'firma': 'Cada flujo lleva la etiqueta de SU ataque; el dataset por ventana lo marca como «multivector».',
        'herramienta': 'varias',
        'intensidad': None,
    },
}


def load_scenarios():
    """Nombres validos, en el orden de scenarios.txt (primera palabra de cada linea)."""
    if not SCENARIOS_FILE.is_file():
        return []
    out = []
    for line in SCENARIOS_FILE.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            out.append(line.split()[0])
    return out


def attack_ids():
    """Ataques individuales: lo que se puede combinar en 'multivector'."""
    return [s for s in load_scenarios() if s not in ('baseline', 'multivector')]


def scenario_info(name):
    base = CATALOGO.get(name, {
        'grupo': 'Otros', 'icono': 'generic', 'nombre': name, 'forma': 'volumen',
        'descripcion': '', 'agota': '', 'firma': '', 'herramienta': '', 'intensidad': None,
    })
    return dict(base, id=name)
