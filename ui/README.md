# Interfaz del banco de pruebas

Configura, lanza y mira una simulación del campus emulado sin escribir comandos.
Llama a Docker directo desde Python, así que funciona igual en `cmd`, PowerShell,
Git Bash, WSL, macOS y Linux.

## Cómo usarla

1. Abre Docker Desktop y espera a que diga «Engine running».
2. Una sola vez: `pip install -r ui/requirements.txt`
3. Desde la raíz del repo: `python ui/app.py`
4. Abre <http://127.0.0.1:8765> (`Ctrl+C` en la terminal para cerrarla).

## Apariencia

Interfaz inspirada en las utilidades de Windows clásico de la época de XP:
superficies grises, selección azul oscuro, bordes rectos y controles con relieve.
Los iconos son SVG originales y todos los recursos funcionan sin internet.
En escritorio, la configuración queda junto a la topología; en pantallas pequeñas
se apilan y el plano de red permite desplazamiento horizontal. El color se reserva
para selección, series y estados.


## Plano de infraestructura

El plano representa borde de Internet (routers y seguridad principal/reserva),
centro de datos (DMZ, portal, racks y control de acceso), distribucion optica
(OLT y ONT), administracion, ocho pabellones y servicios del campus.
Los equipos auxiliares y siete edificios adicionales son ilustrativos: no crean
contenedores, hosts, servicios ni enlaces nuevos en Mininet.

Los cinco grupos originales se presentan como Administracion y Pabellones A–D.
Conservan sus indices, hosts y asociaciones de IP; las cantidades por grupo se
siguen configurando en la interfaz. Las rutas dibujadas pasan por la distribucion
y terminan en el mismo portal. Las tasas y los estados provienen de las metricas
existentes; el plano no mide velocidades opticas ni conmutacion de respaldo.

## Dos módulos

- **Entorno**: revisa Docker, la imagen `ataque-sdn`, el puerto 8080 y el disco, y
  corre la prueba de caminos de red (alumno, infectada y C2 alcanzan el portal).
- **Simulación**: todo en una pantalla.
  - *Configuración* (se pliega a una línea al lanzar): **un ataque** o **varios a la
    vez** (cada PC infectada lanza uno distinto; los flujos se etiquetan con su
    ataque y el dataset por ventana como `multivector`), duración, inicio del
    ataque e intensidades.
  - *Campus*: el plano de la red con paquetes que recorren los enlaces (los
    alumnos en azul, los de ataque en rojo, las respuestas del portal en anillo).
    Cuando hay un ataque cambian el borde, el aviso, el portal y una línea en la
    parte superior de la página. La cantidad de paquetes sale de las métricas reales.
  - *Datos*: tarjetas, gráficos por segundo, resumen antes/durante y archivos.
  - *Dataset de entrenamiento*: al terminar, un botón convierte esa corrida a los dos
    CSV (por flujo y por ventana) y muestra cuántas filas salieron por clase. Solo
    procesa esa corrida (`ONLY_RUNS`), no los demás pcap.

Una simulación deja en `data/` lo mismo que `run_scenario.sh`: pcap, `meta.json` y
los CSV de métricas (`_interno`, `_sdn`, `_docker`). Sin etiqueta, usa `uiHHMMSS`
para no pisar corridas como `r01..r10`.

## Estructura

```
ui/
├── app.py                lanzador (python ui/app.py)
├── requirements.txt
├── server/               backend (Flask)
│   ├── config.py         rutas y constantes
│   ├── catalog.py        explicación de cada escenario (agrega uno aquí)
│   ├── dockerctl.py      hablar con Docker y el sistema
│   ├── launch.py         validar el formulario de lanzamiento
│   ├── datasets.py       convertir una corrida a CSV (flujos y ventanas)
│   ├── jobs.py           la corrida activa (hilo, logs, docker stats)
│   ├── runfiles.py       leer meta.json, métricas y archivos generados
│   └── routes.py         endpoints /api/*
└── web/                  la página (sin build, sin librerías, sin internet)
    ├── index.html
    ├── icons.svg         iconos vectoriales originales, estilo escritorio clásico
    ├── css/              tokens, base, layout, components, entorno, simulacion, campus, charts
    └── js/
        ├── main.js       arranque y sondeo del estado
        ├── core/         dom, api, bus, state, format, router
        ├── entorno/      módulo Entorno
        └── simulacion/   config, campus, packets, stepper, tiles, charts, resumen
```

Agregar un ataque: una línea en `scripts/mininet/scenarios.txt`, su generador en
`capture_campus.py`, y su explicación en `server/catalog.py`.

## Cosas que conviene saber

- **Una sola copia a la vez.** El contenedor siempre se llama `ataque-sdn-run`;
  lanzar otra simulación elimina el anterior. En Windows dos servidores pueden abrir
  el mismo puerto sin avisar, por eso `app.py` no arranca si el puerto está en uso y
  la interfaz se niega a lanzar si hay un contenedor ajeno en marcha.
- Otro puerto: `set UI_PORT=8800` (Windows) o `UI_PORT=8800` (macOS/Linux).
- Las intensidades están acotadas a los rangos estables de Open vSwitch.
- `all` y `repeat` de `run_scenario.sh` siguen corriendo el conjunto base
  (baseline + 4 ataques); los marcados `extra` en `scenarios.txt` se piden por nombre
  o con `SCENARIO_SET=extended`.

## Ataques difíciles de detectar

Con las intensidades por defecto un árbol de 3 niveles ya separa las clases
(F1 0,995): el modelo aprende los números del simulador. **Forma del ataque**
(en Parámetros) cambia cómo ataca la botnet:

| Forma | Qué hace |
|---|---|
| Normal | intensidad fija de siempre (referencia) |
| Baja intensidad | 4-8 pps / 5-8 conexiones por PC, sorteado con la semilla |
| Sigiloso | 1-3 pps, 1 PC por área, HTTP flood que imita a un alumno |
| A pulsos | ráfagas ON 3-6 s / OFF 8-15 s; las ventanas OFF quedan BENIGN |
| Rampa | las PCs se suman de a una durante 40-60 s |

*Carga de alumnos variable* (Opciones adicionales) sortea cuántos alumnos
navegan y su ritmo. Los valores viven en `scripts/mininet/roles.py` (`PERFILES`).

La campaña completa (ataques difíciles + ataques nunca vistos) se corre por
terminal en la PC con Windows: ver `docs/fases_overfitting.md`.

## Falta (siguientes fases)

Biblioteca de corridas anteriores y repeticiones tipo `repeat N` desde la interfaz.
Hoy las campañas largas siguen siendo por terminal (`run_scenario.sh repeat`).
