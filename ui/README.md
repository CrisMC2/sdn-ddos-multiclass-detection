# Interfaz del banco de pruebas

Lanza una corrida del campus emulado, la mira en vivo y la detiene, sin escribir
comandos. Llama a Docker directo desde Python, así que funciona igual en
`cmd`, PowerShell, Git Bash, WSL, macOS y Linux.

## Cómo usarla

1. Abre Docker Desktop y espera a que diga «Engine running».
2. Instala la dependencia (una sola vez): `pip install -r ui/requirements.txt`
3. Desde la raíz del repo: `python ui/app.py`
4. Abre <http://127.0.0.1:8765>

Para cerrarla, `Ctrl+C` en esa terminal.

## Lo que hace

- **Entorno**: revisa Docker, la imagen `ataque-sdn`, el puerto 8080 y el disco, y
  corre la prueba de caminos de red (alumno, infectada y C2 alcanzan el portal).
- **Lanzar**: elige uno de los escenarios de `scripts/mininet/scenarios.txt`
  (agregar uno ahí lo hace aparecer; su explicación vive en `CATALOGO` de `app.py`),
  la duración, el segundo en que arranca el ataque y su intensidad.
- **En vivo**: el campus, el tráfico, la respuesta del portal segundo a segundo, y
  al final un resumen antes/durante el ataque y los archivos generados.

Una corrida deja en `data/` lo mismo que `run_scenario.sh`: pcap, `meta.json` y los
CSV de métricas (`_interno`, `_sdn`, `_docker`). Si no pones etiqueta, usa una
automática `uiHHMMSS`, para no pisar corridas como `r01..r10`.

## Cosas que conviene saber

- **Una sola copia a la vez.** El contenedor siempre se llama `ataque-sdn-run`;
  lanzar otra corrida elimina el anterior. En Windows, además, dos servidores
  pueden abrir el mismo puerto sin avisar. Por eso `app.py` se niega a arrancar si
  el puerto ya está en uso y se niega a lanzar si hay un contenedor ajeno en marcha.
  Si ves una copia vieja, ciérrala con `Ctrl+C` en su terminal.
- **Otro puerto**: `set UI_PORT=8800` (Windows) o `UI_PORT=8800` (macOS/Linux) antes
  de `python ui/app.py`.
- Las intensidades ofrecidas están acotadas a los rangos que se probaron estables en
  Open vSwitch; subirlas a niveles de un ataque real tumba el emulador.
- **Sin internet**: no carga fuentes ni librerías externas.

## Qué falta (siguientes fases)

Convertir a CSV y armar el dataset por ventana desde la interfaz, una biblioteca de
corridas y repeticiones tipo `repeat N`. Hoy eso sigue siendo por terminal
(`run_scenario.sh convert`, `build_windows.py`).
