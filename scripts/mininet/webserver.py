#!/usr/bin/env python3
"""Portal web de la victima.

No es el sitio real de la UNCP. Son cinco paginas fijas para que los
alumnos tengan algo que "navegar" sin salir del laboratorio.

Hay un tope de conexiones y cada pagina tarda PAGE_DELAY_S en
responder. Con eso el flood de las PCs infectadas llena el cupo y los
alumnos empiezan a recibir 503. Sin ese tope, cien peticiones chicas
por segundo no se notarian en esta maquina.
"""
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from roles import MAX_CONNECTIONS, PAGE_DELAY_S, PAGES

_slots = threading.Semaphore(MAX_CONNECTIONS)

BODIES = {
    '/': 'Portal UNCP',
    '/login': 'Intranet - ingreso',
    '/notas': 'Registro de notas',
    '/aula': 'Aula virtual',
    '/biblioteca': 'Biblioteca',
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def handle(self):
        if not _slots.acquire(timeout=1):
            try:
                self.request.sendall(
                    b'HTTP/1.1 503 Service Unavailable\r\n'
                    b'Content-Length: 0\r\n'
                    b'Connection: close\r\n\r\n'
                )
            except OSError:
                pass
            return
        try:
            super(Handler, self).handle()
        finally:
            _slots.release()

    def do_GET(self):
        path = self.path.split('?', 1)[0]
        if path not in BODIES:
            path = '/'
        time.sleep(PAGE_DELAY_S)
        body = (
            '<html><body><h1>%s</h1><p>pagina de prueba del portal</p></body></html>'
            % BODIES[path]
        ).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 80
    if set(BODIES) != set(PAGES):
        raise SystemExit('las paginas del servidor no coinciden con roles.PAGES')
    ThreadingHTTPServer.allow_reuse_address = True
    httpd = ThreadingHTTPServer(('0.0.0.0', port), Handler)
    httpd.daemon_threads = True
    httpd.serve_forever()


if __name__ == '__main__':
    main()
