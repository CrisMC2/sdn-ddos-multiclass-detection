"""Validar el formulario de lanzamiento: convierte el cuerpo JSON que manda la
pagina en (escenario, duracion, variables de entorno del contenedor), o lanza
LaunchError con un mensaje que se le muestra tal cual al usuario."""
import re
import time
from dataclasses import dataclass, field

from .catalog import attack_ids, load_scenarios, scenario_info


class LaunchError(ValueError):
    pass


@dataclass
class Launch:
    scenario: str
    duration: int
    params: dict = field(default_factory=dict)   # variables de entorno del contenedor
    attacks: list = field(default_factory=list)  # vectores en juego (1 o varios)
    onset: int = None

    @property
    def run_name(self):
        tag = self.params.get('RUN_TAG')
        return '%s__%s' % (self.scenario, tag) if tag else self.scenario


def _int(body, key, lo, hi, default=None):
    """Entero acotado a [lo, hi]. Vacio -> default. Invalido -> LaunchError."""
    raw = body.get(key)
    if raw in (None, ''):
        return default
    try:
        val = int(float(raw))
    except (TypeError, ValueError):
        raise LaunchError('«%s» no es un número válido.' % key)
    return max(lo, min(hi, val))


def parse(body):
    scenario = body.get('scenario')
    if scenario not in load_scenarios() + ['verify']:
        raise LaunchError('Escenario inválido: %r' % scenario)

    duration = _int(body, 'duration', 5, 1800, 20)
    onset = _int(body, 'onset_s', 0, 1800, None)
    students = _int(body, 'students_per_area', 1, 9, None)
    bots = _int(body, 'bots_per_area', 1, 9, None)
    seed = _int(body, 'seed', 0, 10 ** 9, None)

    # roles.onset_for ignora el inicio pedido si quedan menos de 10 s de ataque
    # y lo cambia por duration//4 sin avisar. Mejor rechazarlo aqui que dejar
    # que la corrida no haga lo que se pidio.
    if scenario not in ('baseline', 'verify') and onset and duration < onset + 10:
        raise LaunchError(
            'Con %d s de duración el ataque no puede arrancar en el segundo %d: '
            'tienen que quedar al menos 10 s de ataque.' % (duration, onset))

    tag = (body.get('run_tag') or '').strip()
    if tag and not re.fullmatch(r'[A-Za-z0-9_-]{1,24}', tag):
        raise LaunchError('La etiqueta solo admite letras, números, guion y guion bajo (máximo 24).')
    if not tag:
        tag = 'ui%s' % time.strftime('%H%M%S')   # no pisa las corridas r01..rNN

    params = {'RUN_TAG': tag}
    if onset is not None:
        params['ONSET_S'] = onset
    if students is not None:
        params['STUDENTS_PER_AREA'] = students
    if bots is not None:
        params['BOTS_PER_AREA'] = bots
    if seed is not None:
        params['RUN_SEED'] = seed

    # Que vectores intervienen: el propio escenario, o los elegidos si es multivector.
    attacks = []
    if scenario == 'multivector':
        chosen = body.get('attacks')
        if not isinstance(chosen, list):
            raise LaunchError('Elige los ataques que quieres combinar.')
        valid = attack_ids()
        for name in chosen:
            if name not in valid:
                raise LaunchError('Ataque desconocido en la combinación: %r' % name)
            if name not in attacks:
                attacks.append(name)
        if len(attacks) < 2:
            raise LaunchError('Para combinar hay que elegir al menos dos ataques distintos.')
        params['MULTIVECTOR_ATTACKS'] = ','.join(attacks)
    elif scenario not in ('baseline', 'verify'):
        attacks = [scenario]

    # Intensidades: solo las de los vectores en juego, acotadas a rangos estables.
    raw = body.get('intensities') if isinstance(body.get('intensities'), dict) else {}
    for name in attacks:
        inten = scenario_info(name).get('intensidad')
        if not inten:
            continue
        val = _int(raw, inten['env'], inten['min'], inten['max'], None)
        if val is not None:
            params[inten['env']] = val

    return Launch(scenario=scenario, duration=duration, params=params, attacks=attacks, onset=onset)
