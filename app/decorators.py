from functools import wraps
from flask import session, flash, redirect, url_for, request, jsonify

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(*permissions_to_check):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'loggedin' not in session:
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            user_permissions = session.get('permissions', [])
            user_role = session.get('role')

            # ======================================================================
            # ============ INICIO DE LA CORRECCIÓN DEFINITIVA ======================
            # ======================================================================
            # Si el rol del usuario es ADMIN o ARTISAN, se le concede acceso
            # inmediato y se omiten todas las demás comprobaciones.
            if user_role in ['ADMIN', 'ARTISAN']:
                return f(*args, **kwargs)
            # ======================================================================
            # ====================== FIN DE LA CORRECCIÓN ==========================
            # ======================================================================

            # Comprobación de permisos específicos para el resto de roles
            if not any(p in user_permissions for p in permissions_to_check):
                flash('No tienes los permisos necesarios para acceder a esta página.', 'danger')
                return redirect(url_for('production.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def csrf_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if request.method == "POST":
            token = request.form.get("csrf_token") or (request.is_json and request.json.get("csrf_token"))
            if not token or token != session.get("csrf_token"):
                flash("Error de seguridad (CSRF Token inválido).", "danger")
                if request.is_json:
                    return jsonify({'status': 'error', 'message': 'CSRF token missing or incorrect'}), 403
                return redirect(request.url)
        return f(*args, **kwargs)
    return decorated_function