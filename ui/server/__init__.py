"""Interfaz web de Campus-DDoS-SDN (backend).

create_app() arma la aplicacion Flask: sirve la pagina de ui/web/ y la API
en /api. Se arranca con `python ui/app.py`.
"""
from flask import Flask, request, send_from_directory

from .config import WEB_DIR
from .routes import api


def create_app():
    app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path='/static')
    app.register_blueprint(api)

    @app.get('/')
    def index():
        return send_from_directory(str(WEB_DIR), 'index.html')

    @app.after_request
    def no_cache(resp):
        # Servidor local de desarrollo: que un cambio de JS/CSS se vea al
        # recargar, sin pelear con la cache del navegador.
        # El sprite de iconos se usa decenas de veces por pantalla: no se excluye
        # de la cache o el navegador lo pediria en cada <use>.
        if request.path == '/static/icons.svg':
            resp.headers['Cache-Control'] = 'max-age=60'
        elif request.path == '/' or request.path.startswith('/static/'):
            resp.headers['Cache-Control'] = 'no-store'
        return resp

    return app
