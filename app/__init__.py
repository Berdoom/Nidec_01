import os
import sys
import json
import locale
from flask import Flask, session, jsonify, render_template, request, flash, redirect, url_for
from sqlalchemy import create_engine, func, text, inspect
from sqlalchemy.orm import sessionmaker, scoped_session, joinedload
from sqlalchemy.exc import ProgrammingError, OperationalError

# --- Configuración de Rutas para Importación (tu bloque original) ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
print("="*50)
print(f"Directorio actual (__init__.py): {current_dir}")
print(f"Directorio raíz del proyecto añadido al path: {parent_dir}")
print("="*50)
# --- Fin Configuración de Rutas ---

from config import Config

# --- Configuración de la Base de Datos ---
engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'Spanish_Spain')
    except locale.Error:
        print("ADVERTENCIA: Locale 'es_ES' no encontrado.")


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
        
    # --- Configuración de Filtros de Jinja2 ---
    from .utils import to_slug, get_month_name, get_kpi_color_class
    app.jinja_env.filters['fromjson'] = json.loads
    app.jinja_env.filters['slug'] = to_slug
    app.jinja_env.filters['month_name'] = get_month_name
    app.jinja_env.filters['get_kpi_color'] = get_kpi_color_class

    # --- Registro de Blueprints ---
    from .auth import bp as auth_bp
    from .production import bp as production_bp
    from .programa_lm import bp as lm_bp
    from .programa_rotores import bp as rotores_bp
    from .admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(lm_bp, url_prefix='/programa_lm')
    app.register_blueprint(rotores_bp, url_prefix='/programa_rotores')
    app.register_blueprint(admin_bp, url_prefix='/admin')

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db_session.remove()

    @app.before_request
    def before_request_handler():
        session.permanent = True

    @app.context_processor
    def inject_global_vars():
        from .models import Usuario, Pronostico, SolicitudCorreccion, Rol
        
        user = None
        viewable_roles = []
        if 'username' in session:
            user = db_session.query(Usuario).options(
                joinedload(Usuario.role).joinedload(Rol.viewable_roles)
            ).filter_by(username=session['username']).first()
            if user and user.role:
                viewable_roles = [r.nombre for r in user.role.viewable_roles]

        pending_actions_count = 0
        if 'actions.center' in session.get('permissions', []):
            try:
                desviaciones_count = db_session.query(func.count(Pronostico.id)).filter(
                    Pronostico.status == 'Nuevo', Pronostico.razon_desviacion.isnot(None), Pronostico.razon_desviacion != ''
                ).scalar() or 0
                correcciones_count = db_session.query(func.count(SolicitudCorreccion.id)).filter(SolicitudCorreccion.status == 'Pendiente').scalar() or 0
                pending_actions_count = desviaciones_count + correcciones_count
            except Exception as e:
                app.logger.error(f"Error al contar acciones pendientes: {e}")

        return dict(
            current_user=user,
            pending_actions_count=pending_actions_count,
            permissions=session.get('permissions', []),
            viewable_roles=viewable_roles
        )

    @app.cli.command("init-db")
    def init_db_command_wrapper():
        from .models import init_db, create_default_admin
        init_db()
        create_default_admin()
        print("Base de datos inicializada con valores por defecto.")

    return app