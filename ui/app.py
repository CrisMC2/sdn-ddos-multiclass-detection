#!/usr/bin/env python3
"""Lanzador de la interfaz web de Campus-DDoS-SDN.

    python ui/app.py        ->  http://127.0.0.1:8765

La logica esta en ui/server/ (backend) y ui/web/ (pagina). Ver ui/README.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from server import create_app  # noqa: E402
from server.config import UI_PORT  # noqa: E402
from server.dockerctl import port_in_use  # noqa: E402

if __name__ == '__main__':
    # En Windows dos servidores pueden compartir un puerto sin error, y el
    # navegador acaba hablando con la copia vieja sin que nadie se entere.
    if port_in_use(UI_PORT):
        print('*** El puerto %d ya esta en uso: probablemente hay otra copia de la '
              'interfaz abierta en otra terminal.' % UI_PORT)
        print('    Cierrala (Ctrl+C en esa terminal) o usa otro puerto: '
              'set UI_PORT=8800 && python ui/app.py')
        raise SystemExit(1)
    print('*** Interfaz en http://127.0.0.1:%d' % UI_PORT)
    create_app().run(host='127.0.0.1', port=UI_PORT, debug=False, threaded=True)
