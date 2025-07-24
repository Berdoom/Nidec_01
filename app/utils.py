import calendar
from datetime import datetime, timedelta
from flask import session, request
from sqlalchemy import exc

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from pytz import timezone as ZoneInfo

AREAS_IHP = ['Soporte', 'Servicio', 'Cuerpos', 'Flechas', 'Misceláneos', 'Embobinado', 'ECC', 'ERF', 'Carga', 'Output']
AREAS_FHP = ['Rotores Inyección', 'Rotores ERF', 'Cuerpos', 'Flechas', 'Embobinado', 'Barniz', 'Soporte', 'Pintura', 'Carga', 'Output']
HORAS_TURNO = { 'Turno A': ['10AM', '1PM', '4PM'], 'Turno B': ['7PM', '10PM', '12AM'], 'Turno C': ['3AM', '6AM'] }
NOMBRES_TURNOS_PRODUCCION = list(HORAS_TURNO.keys())

def to_slug(text):
    return text.replace(' ', '_').replace('.', '').replace('/', '')

def get_month_name(month_number):
    try:
        return calendar.month_name[int(month_number)]
    except (IndexError, ValueError):
        return ''

def now_mexico():
    try:
        return datetime.now(ZoneInfo("America/Mexico_City"))
    except Exception:
        import pytz
        return datetime.now(pytz.timezone("America/Mexico_City"))

def get_business_date():
    now = now_mexico()
    return (now - timedelta(days=1)).date() if now.hour < 7 else now.date()

def get_kpi_color_class(eficiencia):
    try:
        eficiencia = float(eficiencia)
        if eficiencia < 80: return 'red'
        if eficiencia < 95: return 'yellow'
        return 'green'
    except (ValueError, TypeError):
        return 'red' # Devuelve 'red' por defecto en caso de error

def log_activity(action, details="", area_grupo=None, category="General", severity="Info"):
    from . import db_session
    from .models import ActivityLog
    try:
        log_entry = ActivityLog(
            timestamp=datetime.utcnow(), 
            username=session.get('username', 'Sistema'), 
            action=action, 
            details=details, 
            area_grupo=area_grupo, 
            ip_address=request.remote_addr, 
            category=category, 
            severity=severity
        )
        db_session.add(log_entry)
        db_session.commit()
    except exc.SQLAlchemyError as e:
        db_session.rollback()
        print(f"Error al registrar actividad: {e}")

def get_hourly_target(pronostico_turno, turno_name):
    if not pronostico_turno or pronostico_turno <= 0: return 0
    num_horas = len(HORAS_TURNO.get(turno_name, []))
    return pronostico_turno / num_horas if num_horas > 0 else 0