# app/admin.py

from flask import (Blueprint, render_template, request, redirect, url_for, session,
                   flash, abort, jsonify)
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

from . import db_session
from .decorators import login_required, permission_required, csrf_required
from .utils import log_activity
from .models import (Usuario, Rol, Turno, Permission, ActivityLog,
                     Pronostico, SolicitudCorreccion)
from sqlalchemy import exc
from sqlalchemy.orm import joinedload

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/centro_acciones')
@login_required
@permission_required('actions.center')
def centro_acciones():
    if request.args.get('limpiar'):
        session.pop('acciones_filtros', None)
        return redirect(url_for('admin.centro_acciones'))

    filtros = session.get('acciones_filtros', {})
    if not request.args:
        filtros = {'status': 'Pendientes', 'tipo': 'Todos', 'grupo': 'Todos'}
    elif any(arg in request.args for arg in ['fecha_inicio', 'fecha_fin', 'grupo', 'tipo', 'status']):
        filtros = {
            'fecha_inicio': request.args.get('fecha_inicio'),
            'fecha_fin': request.args.get('fecha_fin'),
            'grupo': request.args.get('grupo'),
            'tipo': request.args.get('tipo', 'Todos'),
            'status': request.args.get('status', 'Pendientes')
        }
    session['acciones_filtros'] = filtros
    items = []

    query_desviaciones = db_session.query(Pronostico, Usuario.nombre_completo).join(Usuario, Pronostico.usuario_razon == Usuario.username, isouter=True).filter(Pronostico.razon_desviacion.isnot(None), Pronostico.razon_desviacion != '')
    query_solicitudes = db_session.query(SolicitudCorreccion, Usuario.nombre_completo).join(Usuario, SolicitudCorreccion.usuario_solicitante == Usuario.username, isouter=True)

    try:
        if filtros.get('fecha_inicio'):
            fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').date()
            query_desviaciones = query_desviaciones.filter(Pronostico.fecha >= fecha_inicio)
            query_solicitudes = query_solicitudes.filter(SolicitudCorreccion.fecha_problema >= fecha_inicio)
        if filtros.get('fecha_fin'):
            fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').date()
            query_desviaciones = query_desviaciones.filter(Pronostico.fecha <= fecha_fin)
            query_solicitudes = query_solicitudes.filter(SolicitudCorreccion.fecha_problema <= fecha_fin)
    except ValueError:
        flash("Formato de fecha inválido.", "warning")

    if filtros.get('grupo') and filtros.get('grupo') != 'Todos':
        query_desviaciones = query_desviaciones.filter(Pronostico.grupo == filtros['grupo'])
        query_solicitudes = query_solicitudes.filter(SolicitudCorreccion.grupo == filtros['grupo'])

    status_filter = filtros.get('status')
    if status_filter == 'Pendientes':
        query_desviaciones = query_desviaciones.filter(Pronostico.status == 'Nuevo')
        query_solicitudes = query_solicitudes.filter(SolicitudCorreccion.status == 'Pendiente')
    elif status_filter and status_filter != 'Todos':
        query_desviaciones = query_desviaciones.filter(Pronostico.status == status_filter)
        query_solicitudes = query_solicitudes.filter(SolicitudCorreccion.status == status_filter)

    if filtros.get('tipo', 'Todos') in ['Todos', 'Desviacion']:
        for d, nombre in query_desviaciones.all():
            items.append({'id': d.id, 'tipo': 'Desviación', 'timestamp': d.fecha_razon, 'fecha_evento': d.fecha, 'grupo': d.grupo, 'area': d.area, 'turno': d.turno, 'usuario': nombre or d.usuario_razon, 'detalles': d.razon_desviacion, 'status': d.status})
    if filtros.get('tipo', 'Todos') in ['Todos', 'Correccion']:
        for s, nombre in query_solicitudes.all():
            items.append({'id': s.id, 'tipo': f"Corrección ({s.tipo_error})", 'timestamp': s.timestamp, 'fecha_evento': s.fecha_problema, 'grupo': s.grupo, 'area': s.area, 'turno': s.turno, 'usuario': nombre or s.usuario_solicitante, 'detalles': s.descripcion, 'status': s.status})
    
    items.sort(key=lambda x: x['timestamp'] if x['timestamp'] else datetime.min, reverse=True)
    return render_template('centro_acciones.html', items=items, filtros=filtros)

@bp.route('/solicitar_correccion', methods=['POST'])
@login_required
@permission_required('captura.access')
@csrf_required
def solicitar_correccion():
    try:
        solicitud = SolicitudCorreccion(
            usuario_solicitante=session.get('username'),
            fecha_problema=datetime.strptime(request.form.get('fecha_problema'), '%Y-%m-%d').date(),
            grupo=request.form.get('grupo'),
            area=request.form.get('area'),
            turno=request.form.get('turno'),
            tipo_error=request.form.get('tipo_error'),
            descripcion=request.form.get('descripcion')
        )
        db_session.add(solicitud)
        log_activity(f"Solicitud Corrección ({request.form.get('tipo_error')})", f"Area: {request.form.get('area')}, Turno: {request.form.get('turno')}", request.form.get('grupo'), 'Datos', 'Warning')
        db_session.commit()
        return jsonify({'status': 'success', 'message': 'Tu solicitud ha sido enviada.'})
    except Exception as e:
        db_session.rollback()
        return jsonify({'status': 'error', 'message': f'Ocurrió un error: {e}'}), 500

@bp.route('/update_reason_status/<int:reason_id>', methods=['POST'])
@login_required
@permission_required('actions.center')
@csrf_required
def update_reason_status(reason_id):
    reason = db_session.get(Pronostico, reason_id)
    if reason and request.form.get('status'):
        old, new = reason.status, request.form.get('status')
        reason.status = new
        log_activity("Cambio Estado (Desviación)", f"ID Razón: {reason.id}. Estado: '{old}' -> '{new}'.", reason.grupo, 'Datos', 'Info')
        db_session.commit()
        flash(f"Estado actualizado a '{new}'.", 'success')
    else:
        flash("No se pudo actualizar el estado.", 'danger')
    return redirect(url_for('admin.centro_acciones'))

@bp.route('/update_solicitud_status/<int:solicitud_id>', methods=['POST'])
@login_required
@permission_required('actions.center')
@csrf_required
def update_solicitud_status(solicitud_id):
    solicitud = db_session.get(SolicitudCorreccion, solicitud_id)
    if solicitud:
        solicitud.status = request.form.get('status')
        solicitud.admin_username = session.get('username')
        solicitud.admin_notas = request.form.get('admin_notas')
        solicitud.fecha_resolucion = datetime.utcnow()
        log_activity("Cambio Estado (Corrección)", f"ID Solicitud: {solicitud.id}. Estado: '{solicitud.status}' -> '{request.form.get('status')}'.", solicitud.grupo, 'Datos', 'Info')
        db_session.commit()
        flash('Estado de la solicitud actualizado.', 'success')
    else:
        flash('No se encontró la solicitud.', 'danger')
    return redirect(url_for('admin.centro_acciones'))

@bp.route('/users', methods=['GET', 'POST'])
@login_required
@permission_required('users.manage')
@csrf_required
def manage_users():
    if request.method == 'POST' and request.form.get('form_type') == 'create_user':
        username, password, role_id, turno_id, nombre, cargo = request.form.get('username'), request.form.get('password'), request.form.get('role_id'), request.form.get('turno_id'), request.form.get('nombre_completo'), request.form.get('cargo')
        if not all([username, password, role_id, nombre, cargo]):
            flash('Todos los campos son obligatorios, excepto el turno.', 'warning')
        elif db_session.query(Usuario).filter_by(username=username).first():
            flash(f"El usuario '{username}' ya existe.", 'danger')
        else:
            turno_id_to_save = int(turno_id) if turno_id else db_session.query(Turno).filter_by(nombre='N/A').one().id
            db_session.add(Usuario(username=username, password=password, role_id=role_id, nombre_completo=nombre, cargo=cargo, turno_id=turno_id_to_save))
            db_session.commit()
            rol = db_session.get(Rol, role_id)
            log_activity("Creación de usuario", f"Usuario '{username}' ({nombre}) creado con rol '{rol.nombre}'.", 'ADMIN', 'Seguridad', 'Info')
            flash(f"Usuario '{username}' creado exitosamente.", 'success')
        return redirect(url_for('admin.manage_users'))

    if request.args.get('limpiar'):
        session.pop('user_filtros', None)
        return redirect(url_for('admin.manage_users'))
        
    filtros = session.get('user_filtros', {})
    if any(arg in request.args for arg in ['username', 'nombre_completo', 'role_id', 'turno_id']):
        filtros = {k: request.args.get(k, '') for k in ['username', 'nombre_completo', 'role_id', 'turno_id']}
        session['user_filtros'] = filtros
        
    query = db_session.query(Usuario).join(Rol).outerjoin(Turno)
    if filtros.get('username'): query = query.filter(Usuario.username.ilike(f"%{filtros['username']}%"))
    if filtros.get('nombre_completo'): query = query.filter(Usuario.nombre_completo.ilike(f"%{filtros['nombre_completo']}%"))
    if filtros.get('role_id'): query = query.filter(Rol.id == filtros['role_id'])
    if filtros.get('turno_id'): query = query.filter(Turno.id == filtros['turno_id'])
    
    users = query.order_by(Usuario.id).all()
    all_roles, all_turnos = db_session.query(Rol).order_by(Rol.nombre).all(), db_session.query(Turno).order_by(Turno.nombre).all()
    return render_template('manage_users.html', users=users, all_roles=all_roles, all_turnos=all_turnos, filtros=filtros)

@bp.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@permission_required('users.manage')
@csrf_required
def edit_user(user_id):
    user = db_session.get(Usuario, user_id)
    if not user: abort(404)
        
    if request.method == 'POST':
        new_username = request.form.get('username')
        if new_username != user.username and db_session.query(Usuario).filter_by(username=new_username).first():
            flash(f"El usuario '{new_username}' ya existe.", 'danger')
        else:
            user.username = new_username
            user.nombre_completo = request.form.get('nombre_completo')
            user.cargo = request.form.get('cargo')
            user.role_id = request.form.get('role_id')
            user.turno_id = int(request.form.get('turno_id')) if request.form.get('turno_id') else db_session.query(Turno).filter_by(nombre='N/A').one().id
            if request.form.get('password'):
                user.password_hash = generate_password_hash(request.form.get('password'))
            try:
                db_session.commit()
                log_activity("Edición de usuario", f"Datos del usuario ID {user.id} ({user.username}) actualizados.", 'ADMIN', 'Seguridad', 'Warning')
                flash('Usuario actualizado correctamente.', 'success')
                return redirect(url_for('admin.manage_users'))
            except exc.IntegrityError as e:
                db_session.rollback()
                flash(f"Error de integridad: {e}", 'danger')
                
    all_roles = db_session.query(Rol).order_by(Rol.nombre).all()
    all_turnos = db_session.query(Turno).order_by(Turno.nombre).all()
    return render_template('edit_user.html', user=user, all_roles=all_roles, all_turnos=all_turnos)

@bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@permission_required('users.manage')
@csrf_required
def delete_user(user_id):
    if user_id == session.get('user_id'):
        flash('No puedes eliminar tu propia cuenta.', 'danger')
    else:
        user = db_session.get(Usuario, user_id)
        if user:
            log_activity("Eliminación de usuario", f"Usuario '{user.username}' (ID: {user_id}) eliminado.", 'ADMIN', 'Seguridad', 'Critical')
            db_session.delete(user)
            db_session.commit()
            flash('Usuario eliminado exitosamente.', 'success')
        else:
            flash('El usuario no existe.', 'danger')
    return redirect(url_for('admin.manage_users'))

@bp.route('/activity_log')
@login_required
@permission_required('logs.view')
def activity_log():
    if request.args.get('limpiar'):
        session.pop('log_filtros', None)
        return redirect(url_for('admin.activity_log'))
        
    filtros = session.get('log_filtros', {})
    if request.args:
        filtros = {'fecha_inicio': request.args.get('fecha_inicio'), 'fecha_fin': request.args.get('fecha_fin'), 'usuario': request.args.get('usuario'), 'area_grupo': request.args.get('area_grupo'), 'category': request.args.get('category'), 'severity': request.args.get('severity')}
    session['log_filtros'] = filtros

    query = db_session.query(ActivityLog, Usuario).outerjoin(Usuario, ActivityLog.username == Usuario.username)
    
    try:
        if filtros.get('fecha_inicio'):
            query = query.filter(ActivityLog.timestamp >= datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d'))
        if filtros.get('fecha_fin'):
            end_date = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(ActivityLog.timestamp < end_date)
    except ValueError:
        flash("Formato de fecha inválido.", "warning")

    if filtros.get('usuario'): query = query.filter(ActivityLog.username.ilike(f"%{filtros['usuario']}%"))
    if filtros.get('area_grupo') and filtros.get('area_grupo') != 'Todos': query = query.filter(ActivityLog.area_grupo == filtros['area_grupo'])
    if filtros.get('category') and filtros.get('category') != 'Todos': query = query.filter(ActivityLog.category == filtros['category'])
    if filtros.get('severity') and filtros.get('severity') != 'Todos': query = query.filter(ActivityLog.severity == filtros['severity'])
    
    logs = query.order_by(ActivityLog.timestamp.desc()).limit(500).all()
    log_categories = ['Autenticación', 'Datos', 'Seguridad', 'Sistema', 'General']
    log_severities = ['Info', 'Warning', 'Critical', 'Error']
    return render_template('activity_log.html', logs=logs, filtros=filtros, log_categories=log_categories, log_severities=log_severities)

@bp.route('/roles', methods=['GET', 'POST'])
@login_required
@permission_required('roles.manage')
@csrf_required
def manage_roles():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        if nombre:
            if not db_session.query(Rol).filter_by(nombre=nombre.upper()).first():
                db_session.add(Rol(nombre=nombre.upper()))
                db_session.commit()
                flash(f"Rol '{nombre.upper()}' creado exitosamente.", 'success')
            else:
                flash(f"El rol '{nombre.upper()}' ya existe.", 'danger')
                
    roles = db_session.query(Rol).order_by(Rol.nombre).all()
    return render_template('manage_roles.html', roles=roles)

@bp.route('/roles/access/<int:role_id>', methods=['GET', 'POST'])
@login_required
@permission_required('roles.manage')
@csrf_required
def manage_role_access(role_id):
    rol_a_editar = db_session.query(Rol).options(joinedload(Rol.viewable_roles)).get(role_id)
    if not rol_a_editar:
        flash("El rol especificado no existe.", "danger")
        return redirect(url_for('admin.manage_roles'))
    
    if rol_a_editar.nombre in ['ADMIN', 'ARTISAN']:
        flash(f"Los accesos del rol {rol_a_editar.nombre} no se pueden modificar.", "info")
        return redirect(url_for('admin.manage_roles'))
        
    if request.method == 'POST':
        selected_role_ids = request.form.getlist('viewable_roles')
        viewable_roles = db_session.query(Rol).filter(Rol.id.in_(selected_role_ids)).all()
        if rol_a_editar not in viewable_roles:
            viewable_roles.append(rol_a_editar)
        rol_a_editar.viewable_roles = viewable_roles
        db_session.commit()
        log_activity("Actualización de Acceso", f"Accesos actualizados para el rol '{rol_a_editar.nombre}'.", 'ADMIN', 'Seguridad', 'Warning')
        flash(f"Los accesos para el rol '{rol_a_editar.nombre}' han sido actualizados.", "success")
        return redirect(url_for('admin.manage_roles'))
        
    EXCLUDED_ROLES = ['ADMIN', 'ARTISAN']
    all_data_groups = db_session.query(Rol).filter(Rol.nombre.notin_(EXCLUDED_ROLES)).order_by(Rol.nombre).all()
    
    return render_template('manage_role_access.html', rol=rol_a_editar, all_data_groups=all_data_groups)

@bp.route('/roles/delete/<int:role_id>', methods=['POST'])
@login_required
@permission_required('roles.manage')
@csrf_required
def delete_role(role_id):
    rol = db_session.get(Rol, role_id)
    if rol:
        if rol.usuarios:
            flash(f"No se puede eliminar el rol '{rol.nombre}' porque tiene usuarios asignados.", 'danger')
        elif rol.nombre in ['ADMIN', 'IHP', 'FHP', 'PROGRAMA_LM', 'ARTISAN', 'PROGRAMA_ROTORES']:
            flash(f"No se puede eliminar el rol de sistema '{rol.nombre}'.", 'danger')
        else:
            db_session.delete(rol)
            db_session.commit()
            flash(f"Rol '{rol.nombre}' eliminado.", 'success')
    else:
        flash("El rol no existe.", 'danger')
    return redirect(url_for('admin.manage_roles'))

@bp.route('/turnos', methods=['GET', 'POST'])
@login_required
@permission_required('users.manage')
@csrf_required
def manage_turnos():
    if request.method == 'POST':
        nombre = request.form.get('nombre')
        if nombre:
            if not db_session.query(Turno).filter_by(nombre=nombre).first():
                db_session.add(Turno(nombre=nombre))
                db_session.commit()
                flash(f"Turno '{nombre}' creado exitosamente.", 'success')
            else:
                flash(f"El turno '{nombre}' ya existe.", 'danger')
                
    turnos = db_session.query(Turno).order_by(Turno.nombre).all()
    return render_template('manage_turnos.html', turnos=turnos)

@bp.route('/turnos/delete/<int:turno_id>', methods=['POST'])
@login_required
@permission_required('users.manage')
@csrf_required
def delete_turno(turno_id):
    turno = db_session.get(Turno, turno_id)
    if turno:
        if turno.usuarios:
            flash(f"No se puede eliminar el turno '{turno.nombre}' porque tiene usuarios asignados.", 'danger')
        else:
            db_session.delete(turno)
            db_session.commit()
            flash(f"Turno '{turno.nombre}' eliminado.", 'success')
    else:
        flash("El turno no existe.", 'danger')
    return redirect(url_for('admin.manage_turnos'))

@bp.route('/roles/permissions/<int:role_id>', methods=['GET', 'POST'])
@login_required
@permission_required('roles.manage')
@csrf_required
def manage_permissions(role_id):
    rol = db_session.query(Rol).options(joinedload(Rol.permissions)).get(role_id)
    if not rol:
        flash("El rol especificado no existe.", "danger")
        return redirect(url_for('admin.manage_roles'))
        
    if request.method == 'POST':
        if rol.nombre == 'ADMIN':
            flash("Los permisos del rol ADMIN no se pueden modificar.", "danger")
            return redirect(url_for('admin.manage_roles'))
            
        selected_permission_ids = request.form.getlist('permissions')
        selected_permissions = db_session.query(Permission).filter(Permission.id.in_(selected_permission_ids)).all()
        rol.permissions = selected_permissions
        db_session.commit()
        log_activity("Actualización de Permisos", f"Permisos actualizados para el rol '{rol.nombre}'.", 'ADMIN', 'Seguridad', 'Warning')
        flash(f"Permisos para el rol '{rol.nombre}' actualizados correctamente.", "success")
        return redirect(url_for('admin.manage_roles'))
        
    all_permissions = db_session.query(Permission).order_by(Permission.name).all()
        
    return render_template('manage_permissions.html', rol=rol, all_permissions=all_permissions)