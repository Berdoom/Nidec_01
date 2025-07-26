import secrets
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from sqlalchemy.orm import joinedload

from . import db_session
from .models import Usuario, Rol
from .utils import log_activity
from .decorators import login_required

bp = Blueprint('auth', __name__)

# ==========================================================
# ====== RUTA DE DEPURACIÓN (AÑADIR TEMPORALMENTE) =========
# ==========================================================
@bp.route('/debug-session')
@login_required
def debug_session():
    # Imprime en la consola del servidor los datos de la sesión actual
    print("\n--- DEBUG DE SESIÓN ---")
    print(f"Usuario: {session.get('username')}")
    print(f"Rol: {session.get('role')}")
    print(f"Permisos: {session.get('permissions')}")
    print("-----------------------\n")
    flash('Los datos de la sesión se han impreso en la consola del servidor.', 'info')
    return redirect(url_for('production.dashboard'))
# ==========================================================

@bp.route('/', methods=['GET', 'POST'])
def login():
    if 'loggedin' in session:
        return redirect(url_for('production.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = db_session.query(Usuario).options(
            joinedload(Usuario.role).joinedload(Rol.permissions),
            joinedload(Usuario.role).joinedload(Rol.viewable_roles)
        ).filter(Usuario.username == username).first()

        if user and user.role and check_password_hash(user.password_hash, password):
            session.clear()
            session.permanent = True
            session['loggedin'] = True
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role.nombre 
            session['nombre_completo'] = user.nombre_completo
            session['permissions'] = [p.name for p in user.role.permissions]
            session['viewable_roles'] = [r.nombre for r in user.role.viewable_roles]
            session['csrf_token'] = secrets.token_hex(16)
            
            log_activity("Inicio de sesión", f"Rol: {user.role.nombre}", 'Sistema', 'Autenticación', 'Info')
            return redirect(url_for('production.dashboard'))
        else:
            log_activity("Intento de inicio de sesión fallido", f"Usuario: '{username}'", 'Sistema', 'Seguridad', 'Warning')
            flash('Usuario o contraseña incorrectos.', 'danger')

    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
        
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    log_activity("Cierre de sesión", "", 'Sistema', 'Autenticación', 'Info')
    session.clear()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('auth.login'))