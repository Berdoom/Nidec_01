from sqlalchemy import func, exc
from datetime import datetime, date, timedelta
import calendar

from . import db_session
from .models import Pronostico, ProduccionCaptura, OutputData
from .utils import HORAS_TURNO, NOMBRES_TURNOS_PRODUCCION, AREAS_IHP, AREAS_FHP, get_hourly_target

def get_group_performance(group_name, start_date_str, end_date_str=None):
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else start_date
        total_pronostico_areas = db_session.query(func.sum(Pronostico.valor_pronostico)).filter(Pronostico.grupo == group_name, Pronostico.fecha.between(start_date, end_date)).scalar() or 0
        total_pronostico_output = db_session.query(func.sum(OutputData.pronostico)).filter(OutputData.grupo == group_name, OutputData.fecha.between(start_date, end_date)).scalar() or 0
        total_producido_areas = db_session.query(func.sum(ProduccionCaptura.valor_producido)).filter(ProduccionCaptura.grupo == group_name, ProduccionCaptura.fecha.between(start_date, end_date)).scalar() or 0
        total_producido_output = db_session.query(func.sum(OutputData.output)).filter(OutputData.grupo == group_name, OutputData.fecha.between(start_date, end_date)).scalar() or 0
        total_pronostico = total_pronostico_areas + total_pronostico_output
        total_producido = total_producido_areas + total_producido_output
        eficiencia = (total_producido / total_pronostico * 100) if total_pronostico > 0 else 0
        return {'pronostico': f"{total_pronostico:,.0f}", 'producido': f"{total_producido:,.0f}", 'eficiencia': round(eficiencia, 2)}
    except Exception as e:
        print(f"ERROR CRÍTICO en get_group_performance para {group_name}: {e}")
        return {'pronostico': '0', 'producido': '0', 'eficiencia': 0}

# ==========================================================
# ============== INICIO DE LA MODIFICACIÓN =================
# ==========================================================
def get_structured_capture_data(group_name, selected_date):
    data_to_render = {}
    try:
        areas_list = AREAS_IHP if group_name == 'IHP' else AREAS_FHP
        
        # 1. Prepara la estructura de datos anidada
        for area in [a for a in areas_list if a != 'Output']:
            data_to_render[area] = {}
            for turno in NOMBRES_TURNOS_PRODUCCION:
                # La estructura ahora incluye un diccionario 'horas'
                data_to_render[area][turno] = {
                    'pronostico': None, 
                    'razon_desviacion': None,
                    'horas': {hora: {'valor': None, 'class': ''} for hora in HORAS_TURNO.get(turno, [])}
                }

        # 2. Rellena los datos de pronóstico y producción
        all_pronosticos = db_session.query(Pronostico).filter_by(fecha=selected_date, grupo=group_name).all()
        for p in all_pronosticos:
            if p.area in data_to_render and p.turno in data_to_render[p.area]:
                data_to_render[p.area][p.turno]['pronostico'] = p.valor_pronostico
                data_to_render[p.area][p.turno]['razon_desviacion'] = p.razon_desviacion

        all_produccion = db_session.query(ProduccionCaptura).filter_by(fecha=selected_date, grupo=group_name).all()
        for prod in all_produccion:
            for turno, horas in HORAS_TURNO.items():
                if prod.hora in horas and prod.area in data_to_render and turno in data_to_render[prod.area]:
                    # Almacena el valor en la estructura anidada
                    data_to_render[prod.area][turno]['horas'][prod.hora]['valor'] = prod.valor_producido
                    break
        
        # 3. Itera sobre la estructura ya poblada para calcular y asignar las clases
        for area, turnos in data_to_render.items():
            for turno_name, turno_data in turnos.items():
                pronostico_turno = turno_data.get('pronostico')
                
                # Calcula la meta por hora para este turno específico
                hourly_target = get_hourly_target(pronostico_turno, turno_name)

                if hourly_target > 0:
                    for hora, hora_data in turno_data['horas'].items():
                        prod_hora = hora_data.get('valor')
                        # Si hay un valor de producción, se le asigna una clase
                        if prod_hora is not None:
                            if prod_hora >= hourly_target:
                                hora_data['class'] = 'input-success'
                            else:
                                hora_data['class'] = 'input-warning'

    except exc.SQLAlchemyError as e:
        print(f"Error al obtener datos estructurados para captura: {e}")
        
    return data_to_render
# ==========================================================
# ================= FIN DE LA MODIFICACIÓN ===================
# ==========================================================

def get_output_data(group, date_str):
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        output_row = db_session.query(OutputData).filter_by(fecha=selected_date, grupo=group).first()
        return {'pronostico': output_row.pronostico or 0, 'output': output_row.output or 0} if output_row else {'pronostico': 0, 'output': 0}
    except (exc.SQLAlchemyError, ValueError) as e:
        print(f"Error al obtener datos de Output: {e}")
        return {'pronostico': 0, 'output': 0}

def get_detailed_performance_data(selected_date):
    performance_data = {'IHP': {}, 'FHP': {}}; all_areas = {'IHP': AREAS_IHP, 'FHP': AREAS_FHP}
    try:
        pronosticos = db_session.query(Pronostico).filter(Pronostico.fecha == selected_date).all()
        produccion_horas = db_session.query(ProduccionCaptura).filter(ProduccionCaptura.fecha == selected_date).all()
        for group, areas in all_areas.items():
            for area in [a for a in areas if a != 'Output']:
                performance_data[group][area] = {}
                for turno in NOMBRES_TURNOS_PRODUCCION:
                    performance_data[group][area][turno] = {'pronostico': None, 'producido': 0, 'eficiencia': 0, 'horas': {hora: {'valor': None, 'class': ''} for hora in HORAS_TURNO.get(turno, [])}}
        for p in pronosticos:
            if p.grupo in performance_data and p.area in performance_data[p.grupo] and p.turno in performance_data[p.grupo][p.area]: performance_data[p.grupo][p.area][p.turno]['pronostico'] = p.valor_pronostico
        for prod in produccion_horas:
            for turno_name, horas_del_turno in HORAS_TURNO.items():
                if prod.hora in horas_del_turno and prod.grupo in performance_data and prod.area in performance_data[prod.grupo] and turno_name in performance_data[prod.grupo][prod.area]:
                    valor = prod.valor_producido or 0
                    performance_data[prod.grupo][prod.area][turno_name]['horas'][prod.hora]['valor'] = valor
                    performance_data[prod.grupo][prod.area][turno_name]['producido'] += valor
                    break
        for group in performance_data:
            for area in performance_data[group]:
                for turno_name, turno_data in performance_data[group][area].items():
                    pronostico_turno = turno_data.get('pronostico')
                    if pronostico_turno is not None and pronostico_turno > 0:
                        turno_data['eficiencia'] = round((turno_data.get('producido', 0) / pronostico_turno) * 100, 1)
                        hourly_target = get_hourly_target(pronostico_turno, turno_name)
                        for hora, hora_data in turno_data.get('horas', {}).items():
                            prod_hora = hora_data.get('valor')
                            if prod_hora is not None and hourly_target > 0:
                                if prod_hora >= hourly_target:
                                    hora_data['class'] = 'text-success font-weight-bold'
                                else:
                                    hora_data['class'] = 'text-warning font-weight-bold'
                    else: turno_data['eficiencia'] = 0
    except exc.SQLAlchemyError as e:
        print(f"Error al generar datos detallados del dashboard: {e}")
    return performance_data

def get_daily_summary(group, target_date):
    try:
        pronostico_areas = db_session.query(func.sum(Pronostico.valor_pronostico)).filter_by(grupo=group, fecha=target_date).scalar() or 0
        pronostico_output = db_session.query(func.sum(OutputData.pronostico)).filter_by(grupo=group, fecha=target_date).scalar() or 0
        producido_areas = db_session.query(func.sum(ProduccionCaptura.valor_producido)).filter_by(grupo=group, fecha=target_date).scalar() or 0
        producido_output = db_session.query(func.sum(OutputData.output)).filter_by(grupo=group, fecha=target_date).scalar() or 0
        total_pronostico = pronostico_areas + pronostico_output
        total_producido = producido_areas + producido_output
        eficiencia = (total_producido / total_pronostico * 100) if total_pronostico > 0 else 0
        return {'pronostico': total_pronostico, 'producido': total_producido, 'eficiencia': eficiencia}
    except Exception as e:
        print(f"Error en get_daily_summary: {e}")
        return {'pronostico': 0, 'producido': 0, 'eficiencia': 0}