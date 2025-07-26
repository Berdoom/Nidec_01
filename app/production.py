# app/production.py

from flask import (Blueprint, render_template, request, redirect, url_for, session,
                   flash, jsonify, send_file, abort)
from datetime import datetime, timedelta, date
import calendar
import pandas as pd
import io

from . import db_session, services
from .decorators import login_required, permission_required, csrf_required
from .utils import (log_activity, get_business_date, AREAS_IHP, AREAS_FHP,
                    NOMBRES_TURNOS_PRODUCCION, HORAS_TURNO, to_slug, now_mexico)
from .models import Pronostico, ProduccionCaptura, OutputData, SolicitudCorreccion
from sqlalchemy import exc

bp = Blueprint('production', __name__)


@bp.route('/dashboard')
@login_required
def dashboard():
    perms = session.get('permissions', [])
    
    if 'dashboard.view.admin' in perms:
        return redirect(url_for('production.dashboard_admin'))
    
    if 'dashboard.view.group' in perms:
        user_role = session.get('role')
        if user_role in ['IHP', 'FHP']:
            return redirect(url_for('production.dashboard_group', group=user_role.lower()))
        
        viewable = session.get('viewable_roles', [])
        for role_name in viewable:
            if role_name in ['IHP', 'FHP']:
                return redirect(url_for('production.dashboard_group', group=role_name.lower()))

    if 'programa_lm.view' in perms:
        return redirect(url_for('lm.programa_lm'))
    
    if 'programa_rotores.view' in perms:
        return redirect(url_for('rotores.programa_rotores'))
    
    flash('No tienes permisos para ver ningún dashboard o programa principal. Se ha cerrado tu sesión.', 'warning')
    log_activity("Cierre de sesión automático", "Usuario sin permisos de dashboard/programa.", 'Sistema', 'Seguridad', 'Warning')
    session.clear()
    return redirect(url_for('auth.login'))

@bp.route('/dashboard/admin')
@login_required
@permission_required('dashboard.view.admin')
def dashboard_admin():
    selected_date_str = request.args.get('fecha', get_business_date().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Formato de fecha inválido, mostrando datos de hoy.", "warning")
        selected_date_str = get_business_date().strftime('%Y-%m-%d')
        selected_date = get_business_date()

    ihp_kpi_data = services.get_group_performance('IHP', selected_date_str)
    fhp_kpi_data = services.get_group_performance('FHP', selected_date_str)
    
    try:
        total_pronostico = int(ihp_kpi_data['pronostico'].replace(',', '')) + int(fhp_kpi_data['pronostico'].replace(',', ''))
        total_producido = int(ihp_kpi_data['producido'].replace(',', '')) + int(fhp_kpi_data['producido'].replace(',', ''))
    except (ValueError, KeyError):
        total_pronostico, total_producido = 0, 0
        flash("Hubo un error al calcular los totales globales.", "danger")

    total_eficiencia = (total_producido / total_pronostico * 100) if total_pronostico > 0 else 0
    
    global_kpis = {'pronostico': f"{total_pronostico:,.0f}", 'producido': f"{total_producido:,.0f}", 'eficiencia': round(total_eficiencia, 2)}
    performance_data = services.get_detailed_performance_data(selected_date)
    output_data_ihp = services.get_output_data('IHP', selected_date_str)
    output_data_fhp = services.get_output_data('FHP', selected_date_str)
    
    return render_template('dashboard_admin.html', 
                           selected_date=selected_date_str, 
                           global_kpis=global_kpis, 
                           ihp_data=ihp_kpi_data, fhp_data=fhp_kpi_data, 
                           performance_data=performance_data, 
                           output_data_ihp=output_data_ihp, output_data_fhp=output_data_fhp, 
                           nombres_turnos=NOMBRES_TURNOS_PRODUCCION, 
                           horas_turno=HORAS_TURNO, 
                           AREAS_IHP=AREAS_IHP, AREAS_FHP=AREAS_FHP)

@bp.route('/dashboard/<group>')
@login_required
@permission_required('dashboard.view.group')
def dashboard_group(group):
    group_upper = group.upper()
    if group_upper not in ['IHP', 'FHP']: abort(404)
    if group_upper not in session.get('viewable_roles', []): 
        flash('No tienes permiso para ver el dashboard de este grupo.', 'danger')
        return redirect(url_for('production.dashboard'))
    
    selected_date_str = request.args.get('fecha', get_business_date().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Formato de fecha inválido, mostrando datos de hoy.", "warning")
        selected_date_str = get_business_date().strftime('%Y-%m-%d')
        selected_date = get_business_date()

    yesterday_str = (selected_date - timedelta(days=1)).strftime('%Y-%m-%d')
    summary_today = services.get_group_performance(group_upper, selected_date_str)
    summary_yesterday = services.get_group_performance(group_upper, yesterday_str)

    try:
        prod_today_num = int(summary_today['producido'].replace(',', ''))
        prod_yesterday_num = int(summary_yesterday['producido'].replace(',', ''))
        summary_today['trend'] = 'up' if prod_today_num > prod_yesterday_num else 'down' if prod_today_num < prod_yesterday_num else 'stable'
    except (ValueError, KeyError):
        summary_today['trend'] = 'stable'

    all_performance_data = services.get_detailed_performance_data(selected_date)
    group_performance_data = all_performance_data.get(group_upper, {})
    output_data = services.get_output_data(group_upper, selected_date_str)
    areas_list = [a for a in (AREAS_IHP if group_upper == 'IHP' else AREAS_FHP) if a != 'Output']
    
    return render_template('dashboard_group.html', 
                           summary=summary_today, 
                           areas=areas_list, 
                           nombres_turnos=NOMBRES_TURNOS_PRODUCCION, 
                           horas_turno=HORAS_TURNO, 
                           selected_date=selected_date_str, 
                           group_name=group_upper, 
                           performance_data=group_performance_data, 
                           output_data=output_data)



@bp.route('/reportes')
@login_required
@permission_required('reportes.view')
def reportes():
    is_admin = 'admin.access' in session.get('permissions', [])
    user_role = session.get('role')
    default_group = user_role if user_role in ['IHP', 'FHP'] else session.get('viewable_roles', ['IHP'])[0]
    group = request.args.get('group', default_group)
    if not is_admin and group not in session.get('viewable_roles', []): 
        group = default_group

    # Parámetros simplificados
    today = get_business_date()
    selected_date_str = request.args.get('date', today.strftime('%Y-%m-%d'))
    selected_area = request.args.get('area', 'GENERAL')  # GENERAL, o área específica
    
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = today
        selected_date_str = today.strftime('%Y-%m-%d')

    # Obtener datos optimizados
    weekly_data, monthly_data = services.get_optimized_report_data(group, selected_area, selected_date)
    
    # Obtener datos detallados del día específico para la tabla
    daily_data = services.get_daily_detailed_data(group, selected_area, selected_date)
    
    context = {
        'group': group,
        'selected_area': selected_area,
        'selected_date': selected_date_str,
        'is_admin': is_admin,
        'weekly_data': weekly_data,
        'monthly_data': monthly_data,
        'daily_data': daily_data,
        'AREAS_IHP': [a for a in AREAS_IHP if a != 'Output'],
        'AREAS_FHP': [a for a in AREAS_FHP if a != 'Output']
    }

    return render_template('reportes.html', **context)

@bp.route('/captura/<group>', methods=['GET', 'POST'])
@login_required
@permission_required('captura.access')
@csrf_required
def captura(group):
    group_upper = group.upper()
    if group_upper not in ['IHP', 'FHP']: abort(404)
    if group_upper not in session.get('viewable_roles', []):
        flash(f'No tienes permiso para capturar datos del grupo {group_upper}.', 'danger')
        return redirect(url_for('production.dashboard'))
    
    areas_list = AREAS_IHP if group_upper == 'IHP' else AREAS_FHP

    if request.method == 'POST':
        selected_date_str = request.form.get('fecha')
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash("Fecha inválida en el formulario.", "danger")
            return redirect(url_for('production.captura', group=group))
        
        now_dt, changes_detected = now_mexico(), False
        try:
            for area in [a for a in areas_list if a != 'Output']:
                for turno in NOMBRES_TURNOS_PRODUCCION:
                    new_val_str = request.form.get(f'pronostico_{to_slug(area)}_{to_slug(turno)}')
                    if new_val_str and new_val_str.isdigit():
                        new_val = int(new_val_str)
                        existing = db_session.query(Pronostico).filter_by(fecha=selected_date, grupo=group_upper, area=area, turno=turno).first()
                        if existing:
                            if (existing.valor_pronostico or 0) != new_val:
                                old_val = existing.valor_pronostico
                                existing.valor_pronostico = new_val
                                changes_detected = True
                                log_activity("Modificación Pronóstico", f"Area: {area}, Turno: {turno}. Valor: {old_val} -> {new_val}", group_upper, 'Datos', 'Info')
                        else:
                            db_session.add(Pronostico(fecha=selected_date, grupo=group_upper, area=area, turno=turno, valor_pronostico=new_val))
                            changes_detected = True
                            log_activity("Creación Pronóstico", f"Area: {area}, Turno: {turno}. Valor: {new_val}", group_upper, 'Datos', 'Info')

            for area in [a for a in areas_list if a != 'Output']:
                for turno in NOMBRES_TURNOS_PRODUCCION:
                    for hora in HORAS_TURNO.get(turno, []):
                        new_val_str = request.form.get(f'produccion_{to_slug(area)}_{hora}')
                        if new_val_str and new_val_str.isdigit():
                            new_val = int(new_val_str)
                            existing = db_session.query(ProduccionCaptura).filter_by(fecha=selected_date, grupo=group_upper, area=area, hora=hora).first()
                            if existing:
                                if (existing.valor_producido or 0) != new_val:
                                    old_val = existing.valor_producido
                                    existing.valor_producido = new_val
                                    existing.usuario_captura = session.get('username')
                                    existing.fecha_captura = now_dt
                                    changes_detected = True
                                    log_activity("Modificación Producción", f"Area: {area}, Hora: {hora}. Valor: {old_val} -> {new_val}", group_upper, 'Datos', 'Info')
                            else:
                                db_session.add(ProduccionCaptura(fecha=selected_date, grupo=group_upper, area=area, hora=hora, valor_producido=new_val, usuario_captura=session.get('username'), fecha_captura=now_dt))
                                changes_detected = True
                                log_activity("Creación Producción", f"Area: {area}, Hora: {hora}. Valor: {new_val}", group_upper, 'Datos', 'Info')

            try:
                pronostico_output_raw = request.form.get('pronostico_output')
                produccion_output_raw = request.form.get('produccion_output')
                new_pron_out = None
                new_prod_out = None
                if pronostico_output_raw is not None and pronostico_output_raw != '':
                    new_pron_out = int(pronostico_output_raw)
                if produccion_output_raw is not None and produccion_output_raw != '':
                    new_prod_out = int(produccion_output_raw)
            except (ValueError, TypeError):
                new_pron_out, new_prod_out = None, None
                flash("Se detectó un valor no numérico en los campos de Output.", "warning")

            existing_output = db_session.query(OutputData).filter_by(fecha=selected_date, grupo=group_upper).first()

            if existing_output:
                updated = False
                if new_pron_out is not None and existing_output.pronostico != new_pron_out:
                    existing_output.pronostico = new_pron_out
                    updated = True
                if new_prod_out is not None and existing_output.output != new_prod_out:
                    existing_output.output = new_prod_out
                    updated = True
                if updated:
                    existing_output.usuario_captura = session.get('username')
                    existing_output.fecha_captura = now_dt
                    changes_detected = True
                    log_activity("Actualización Output", f"Pron: {new_pron_out}, Prod: {new_prod_out}", group_upper, 'Datos', 'Info')
            elif (new_pron_out is not None and new_pron_out > 0) or (new_prod_out is not None and new_prod_out > 0):
                db_session.add(OutputData(
                    fecha=selected_date,
                    grupo=group_upper,
                    pronostico=new_pron_out if new_pron_out is not None else 0,
                    output=new_prod_out if new_prod_out is not None else 0,
                    usuario_captura=session.get('username'),
                    fecha_captura=now_dt
                ))
                changes_detected = True
                log_activity("Creación Output", f"Pron: {new_pron_out}, Prod: {new_prod_out}", group_upper, 'Datos', 'Info')
            
            db_session.commit()
            if changes_detected:
                flash('Cambios guardados exitosamente.', 'success')
            else:
                flash('No se detectaron cambios.', 'info')
        except exc.SQLAlchemyError as e:
            db_session.rollback()
            flash(f"Error al guardar en la base de datos: {e}", 'danger')
        
        return redirect(url_for('production.captura', group=group, fecha=selected_date_str))
    
    selected_date_str = request.args.get('fecha', get_business_date().strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        flash("Formato de fecha inválido, mostrando datos de hoy.", "warning")
        selected_date_str = get_business_date().strftime('%Y-%m-%d')
        selected_date = get_business_date()
        
    data_for_template = services.get_structured_capture_data(group_upper, selected_date)
    output_data = services.get_output_data(group_upper, selected_date_str)
    
    return render_template('captura_group.html', 
                           areas=areas_list, 
                           horas_turno=HORAS_TURNO, 
                           nombres_turnos=NOMBRES_TURNOS_PRODUCCION, 
                           selected_date=selected_date_str, 
                           data=data_for_template, 
                           output_data=output_data, 
                           group_name=group_upper)

@bp.route('/submit_reason', methods=['POST'])
@login_required
@permission_required('captura.access')
@csrf_required
def submit_reason():
    try:
        date_str = request.form.get('date')
        area = request.form.get('area')
        group = request.form.get('group')
        turno_name = request.form.get('turno_name')
        reason = request.form.get('reason')
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        pronostico_entry = db_session.query(Pronostico).filter_by(fecha=selected_date, grupo=group.upper(), area=area, turno=turno_name).first()
        if pronostico_entry:
            pronostico_entry.razon_desviacion = reason
            pronostico_entry.usuario_razon = session.get('username')
            pronostico_entry.fecha_razon = datetime.utcnow()
            pronostico_entry.status = 'Nuevo'
            db_session.commit()
            log_activity("Justificación Desviación", f"Area: {area}, Turno: {turno_name}", group, 'Datos', 'Info')
            return jsonify({'status': 'success', 'message': 'La razón ha sido guardada exitosamente.'})
        else:
            return jsonify({'status': 'error', 'message': 'No se encontró el registro de pronóstico para actualizar.'}), 404
    except Exception as e:
        db_session.rollback()
        log_activity("Error Justificación", str(e), "Sistema", "Error", "Critical")
        return jsonify({'status': 'error', 'message': f'Ocurrió un error en el servidor: {e}'}), 500



@bp.route('/borrar_datos_fecha/<group>/<fecha>', methods=['POST'])
@login_required
@permission_required('borrado.maestro')
@csrf_required
def borrar_datos_fecha(group, fecha):
    group_upper = group.upper()
    try:
        selected_date = datetime.strptime(fecha, '%Y-%m-%d').date()
    except ValueError:
        flash("Formato de fecha inválido.", "danger")
        return redirect(url_for('production.captura', group=group))

    try:
        db_session.query(ProduccionCaptura).filter_by(fecha=selected_date, grupo=group_upper).delete()
        db_session.query(Pronostico).filter_by(fecha=selected_date, grupo=group_upper).delete()
        db_session.query(OutputData).filter_by(fecha=selected_date, grupo=group_upper).delete()
        db_session.commit()
        log_activity("Borrado Masivo de Datos", f"Se eliminaron todos los datos del grupo {group_upper} para la fecha {fecha}.", group_upper, 'Seguridad', 'Critical')
        flash(f"Todos los datos de producción para el grupo {group_upper} del día {fecha} han sido eliminados.", "success")
    except Exception as e:
        db_session.rollback()
        log_activity("Error en Borrado Masivo", f"Error al intentar borrar datos: {e}", group_upper, "Error", "Critical")
        flash(f"Ocurrió un error al intentar eliminar los datos: {e}", "danger")
        
    return redirect(url_for('production.captura', group=group, fecha=fecha))