# app/models.py

import os
import sys
from sqlalchemy import (create_engine, Column, Integer, String, Float, DateTime,
                        ForeignKey, Date, Text, inspect, text, UniqueConstraint, Boolean, Table)
from sqlalchemy.orm import sessionmaker, declarative_base, scoped_session, relationship
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError, NoSuchTableError
from werkzeug.security import generate_password_hash
from datetime import datetime
from dotenv import load_dotenv

try:
    from . import db_session, engine
except ImportError:
    print("ADVERTENCIA: Ejecutando models.py como un script independiente. Configurando el entorno manualmente...")
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    sys.path.append(project_root)
    from config import Config
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Base.query = db_session.query_property()

role_permissions = Table('role_permissions', Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('permission_id', Integer, ForeignKey('permissions.id', ondelete='CASCADE'), primary_key=True)
)
role_viewable_roles = Table('role_viewable_roles', Base.metadata,
    Column('role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True),
    Column('viewable_role_id', Integer, ForeignKey('roles.id', ondelete='CASCADE'), primary_key=True)
)

class Permission(Base):
    __tablename__ = 'permissions'
    id = Column(Integer, primary_key=True); name = Column(String(100), unique=True, nullable=False, index=True); description = Column(String(255))

class Rol(Base):
    __tablename__ = 'roles'
    id = Column(Integer, primary_key=True)
    nombre = Column(String(50), unique=True, nullable=False)
    permissions = relationship('Permission', secondary=role_permissions, backref='roles', lazy='subquery')
    viewable_roles = relationship('Rol', secondary=role_viewable_roles, primaryjoin=id == role_viewable_roles.c.role_id, secondaryjoin=id == role_viewable_roles.c.viewable_role_id, backref='viewed_by_roles')

class Turno(Base): __tablename__ = 'turnos'; id = Column(Integer, primary_key=True); nombre = Column(String(50), unique=True, nullable=False)
class Usuario(Base):
    __tablename__ = 'usuarios'
    id = Column(Integer, primary_key=True); username = Column(String(80), unique=True, nullable=False); password_hash = Column(String(256), nullable=False); nombre_completo = Column(String(120), nullable=True); cargo = Column(String(80), nullable=True); role_id = Column(Integer, ForeignKey('roles.id')); turno_id = Column(Integer, ForeignKey('turnos.id'))
    role = relationship('Rol', backref='usuarios'); turno = relationship('Turno', backref='usuarios')
    def __init__(self, username, password, role_id, nombre_completo=None, cargo=None, turno_id=None): self.username = username; self.password_hash = generate_password_hash(password); self.role_id = role_id; self.nombre_completo = nombre_completo; self.cargo = cargo; self.turno_id = turno_id

class OrdenLM(Base):
    __tablename__ = 'ordenes_lm'
    id = Column(Integer, primary_key=True)
    wip_order = Column(String(100), unique=True, nullable=False)
    item = Column(String(100))
    qty = Column(Integer, nullable=False, default=1)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(50), default='Pendiente', nullable=False, index=True)
    celdas = relationship('DatoCeldaLM', backref='orden', cascade='all, delete-orphan')

class ColumnaLM(Base):
    __tablename__ = 'columnas_lm'
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), unique=True, nullable=False)
    orden = Column(Integer, default=100)
    editable_por_lm = Column(Boolean, default=True, nullable=False)
    ancho_columna = Column(Integer, default=180) 
    celdas = relationship('DatoCeldaLM', backref='columna', cascade='all, delete-orphan')

class DatoCeldaLM(Base):
    __tablename__ = 'datos_celda_lm'
    id = Column(Integer, primary_key=True)
    orden_id = Column(Integer, ForeignKey('ordenes_lm.id', ondelete='CASCADE'), nullable=False)
    columna_id = Column(Integer, ForeignKey('columnas_lm.id', ondelete='CASCADE'), nullable=False)
    valor = Column(Text)
    estilos_css = Column(Text, nullable=True)
    __table_args__ = (UniqueConstraint('orden_id', 'columna_id', name='_orden_columna_uc'),)

class OrdenRotores(Base):
    __tablename__ = 'ordenes_rotores'
    id = Column(Integer, primary_key=True)
    item = Column(String(100), unique=True, nullable=False)
    item_number = Column(String(100))
    cantidad = Column(Integer, nullable=False, default=1)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(50), default='Pendiente', nullable=False, index=True)
    celdas = relationship('DatoCeldaRotores', backref='orden', cascade='all, delete-orphan')

class ColumnaRotores(Base):
    __tablename__ = 'columnas_rotores'
    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), unique=True, nullable=False)
    orden = Column(Integer, default=100)
    celdas = relationship('DatoCeldaRotores', backref='columna', cascade='all, delete-orphan')

class DatoCeldaRotores(Base):
    __tablename__ = 'datos_celda_rotores'
    id = Column(Integer, primary_key=True)
    orden_id = Column(Integer, ForeignKey('ordenes_rotores.id', ondelete='CASCADE'), nullable=False)
    columna_id = Column(Integer, ForeignKey('columnas_rotores.id', ondelete='CASCADE'), nullable=False)
    valor = Column(Text)
    estilos_css = Column(Text, nullable=True)
    __table_args__ = (UniqueConstraint('orden_id', 'columna_id', name='_orden_rotor_columna_uc'),)

class Pronostico(Base): __tablename__ = 'pronosticos'; id = Column(Integer, primary_key=True); fecha = Column(Date, nullable=False, index=True); grupo = Column(String(10), nullable=False, index=True); area = Column(String(50), nullable=False); turno = Column(String(20), nullable=False); valor_pronostico = Column(Integer); razon_desviacion = Column(Text); usuario_razon = Column(String(80)); fecha_razon = Column(DateTime); status = Column(String(50), default='Nuevo', index=True); __table_args__ = (UniqueConstraint('fecha', 'grupo', 'area', 'turno', name='_fecha_grupo_area_turno_uc'),)
class ProduccionCaptura(Base): __tablename__ = 'produccion_capturas'; id = Column(Integer, primary_key=True); fecha = Column(Date, nullable=False, index=True); grupo = Column(String(10), nullable=False, index=True); area = Column(String(50), nullable=False); hora = Column(String(10), nullable=False); valor_producido = Column(Integer); usuario_captura = Column(String(80)); fecha_captura = Column(DateTime, default=datetime.utcnow); __table_args__ = (UniqueConstraint('fecha', 'grupo', 'area', 'hora', name='_fecha_grupo_area_hora_uc'),)
class ActivityLog(Base): __tablename__ = 'activity_logs'; id = Column(Integer, primary_key=True); timestamp = Column(DateTime, default=datetime.utcnow, index=True); username = Column(String(80), index=True); action = Column(String(255)); details = Column(Text); area_grupo = Column(String(50), index=True); ip_address = Column(String(45)); category = Column(String(50)); severity = Column(String(20))
class OutputData(Base): __tablename__ = 'output_data'; id = Column(Integer, primary_key=True); fecha = Column(Date, nullable=False, index=True); grupo = Column(String(10), nullable=False, index=True); pronostico = Column(Integer); output = Column(Integer); usuario_captura = Column(String(80)); fecha_captura = Column(DateTime, default=datetime.utcnow)
class SolicitudCorreccion(Base): __tablename__ = 'solicitudes_correccion'; id = Column(Integer, primary_key=True); timestamp = Column(DateTime, default=datetime.utcnow, index=True); usuario_solicitante = Column(String(80), nullable=False); fecha_problema = Column(Date, nullable=False); grupo = Column(String(10), nullable=False); area = Column(String(50)); turno = Column(String(20)); tipo_error = Column(String(100), nullable=False); descripcion = Column(Text, nullable=False); status = Column(String(50), default='Pendiente', index=True); admin_username = Column(String(80)); fecha_resolucion = Column(DateTime); admin_notas = Column(Text)

def init_db():
    print("Verificando y creando tablas si es necesario...")
    Base.metadata.create_all(bind=engine)
    print("Verificación de tablas completada.")

def create_default_admin():
    print("Iniciando verificación y creación de datos por defecto...")
    try:
        # Añade el nuevo rol 'IHP_ROTORES' a la lista de roles que se crean por defecto.
        default_roles = ['ADMIN', 'IHP', 'FHP', 'PROGRAMA_LM', 'PROGRAMA_ROTORES', 'ARTISAN', 'IHP_ROTORES']
        
        for role_name in default_roles:
            if not db_session.query(Rol).filter_by(nombre=role_name).first(): db_session.add(Rol(nombre=role_name))
        
        default_turnos = ['Turno A', 'Turno B', 'Turno C', 'N/A']
        for turno_name in default_turnos:
            if not db_session.query(Turno).filter_by(nombre=turno_name).first(): db_session.add(Turno(nombre=turno_name))
        db_session.commit()

        DEFAULT_PERMISSIONS = {
            'admin.access': 'Acceso global a todas las funciones.', 'dashboard.view.admin': 'Ver el dashboard de administrador.', 'dashboard.view.group': 'Ver dashboards de grupo (IHP/FHP).',
            'captura.access': 'Acceder a las páginas de captura.', 'registro.view': 'Ver las páginas de registro de producción.', 'reportes.view': 'Ver la página de reportes.',
            'programa_lm.view': 'Ver el programa LM.', 'programa_lm.edit': 'Editar celdas y estado en programa LM.',
            'programa_rotores.view': 'Ver el programa de Rotores.', 'programa_rotores.edit': 'Editar celdas y estado en programa de Rotores.',
            'users.manage': 'Gestionar usuarios.', 'roles.manage': 'Gestionar roles y permisos.', 'logs.view': 'Ver el log de actividad.', 'actions.center': 'Gestionar el centro de acciones.',
            'borrado.maestro': 'Permiso único para el borrado masivo de datos.'
        }
        for name, desc in DEFAULT_PERMISSIONS.items():
            if not db_session.query(Permission).filter_by(name=name).first(): db_session.add(Permission(name=name, description=desc))
        db_session.commit()
        
        artisan_perms = list(DEFAULT_PERMISSIONS.keys())
        admin_perms = [p for p in DEFAULT_PERMISSIONS.keys() if p != 'borrado.maestro']

        # Define la lista de permisos para cada rol, incluyendo el nuevo.
        PERMISSIONS_FOR_ROLE = {
            'ARTISAN': artisan_perms, 
            'ADMIN': admin_perms,
            'IHP': ['dashboard.view.group', 'captura.access', 'registro.view', 'reportes.view', 'programa_lm.view', 'programa_rotores.view'],
            'FHP': ['dashboard.view.group', 'captura.access', 'registro.view', 'reportes.view', 'programa_lm.view', 'programa_rotores.view'],
            'PROGRAMA_LM': ['programa_lm.view', 'programa_lm.edit'],
            'PROGRAMA_ROTORES': ['programa_rotores.view', 'programa_rotores.edit'],
            'IHP_ROTORES': [
                'dashboard.view.group', 'captura.access', 'registro.view', 'reportes.view',
                'programa_rotores.view', 'programa_rotores.edit'
            ]
        }
        
        for role_name, perm_names in PERMISSIONS_FOR_ROLE.items():
            role = db_session.query(Rol).filter_by(nombre=role_name).one_or_none();
            if role:
                role.permissions.clear();
                for perm_name in perm_names:
                    perm = db_session.query(Permission).filter_by(name=perm_name).one(); role.permissions.append(perm)
        db_session.commit()
        
        # Define a qué grupos de datos puede ver el nuevo rol.
        VIEWABLE_ROLES_FOR_ROLE = {
            'IHP_ROTORES': ['IHP', 'PROGRAMA_ROTORES']
        }
        
        for role_name, viewable_names in VIEWABLE_ROLES_FOR_ROLE.items():
            role = db_session.query(Rol).filter_by(nombre=role_name).one_or_none()
            if role:
                # Limpia la lista actual por si se está reinicializando
                current_viewable = {r.nombre for r in role.viewable_roles}
                
                # Siempre se debe poder ver a sí mismo
                if role.nombre not in current_viewable:
                    role.viewable_roles.append(role)
                    
                for viewable_name in viewable_names:
                    if viewable_name not in current_viewable:
                        viewable_role = db_session.query(Rol).filter_by(nombre=viewable_name).one_or_none()
                        if viewable_role:
                            role.viewable_roles.append(viewable_role)
        db_session.commit()

        if db_session.query(ColumnaRotores).count() == 0:
            print("Creando columnas por defecto para Programa Rotores...")
            columnas_rotores = ['Rotor', 'Lamina', 'Flecha', 'Comentarios']
            for i, nombre in enumerate(columnas_rotores):
                db_session.add(ColumnaRotores(nombre=nombre, orden=i))
            db_session.commit()
            print("Columnas de Rotores creadas.")

        print("Configurando visibilidad de roles por defecto...")
        all_roles_q = db_session.query(Rol).all()
        admin_role = next((r for r in all_roles_q if r.nombre == 'ADMIN'), None)
        artisan_role = next((r for r in all_roles_q if r.nombre == 'ARTISAN'), None)
        for role in all_roles_q:
            if role not in role.viewable_roles: role.viewable_roles.append(role)
            if admin_role and role not in admin_role.viewable_roles: admin_role.viewable_roles.append(role)
            if artisan_role and role not in artisan_role.viewable_roles: artisan_role.viewable_roles.append(role)
        db_session.commit()
        print("Visibilidad por defecto configurada.")
        
        na_turno = db_session.query(Turno).filter_by(nombre='N/A').one_or_none()
        if admin_role and not db_session.query(Usuario).filter_by(role_id=admin_role.id).first():
            if not db_session.query(Usuario).filter_by(username='admin').first():
                print("Creando usuario 'admin' por defecto...")
                default_admin = Usuario(username='admin', password='password', role_id=admin_role.id, nombre_completo='Administrador', cargo='System Admin', turno_id=na_turno.id if na_turno else None)
                db_session.add(default_admin)
                print("Usuario 'admin' creado.")
        
        if artisan_role:
             if not db_session.query(Usuario).filter_by(username='GCL1909').first():
                print("Creando usuario 'GCL1909' con rol ARTISAN...")
                default_artisan = Usuario(username='GCL1909', password='1909', role_id=artisan_role.id, nombre_completo='Usuario Maestro', cargo='Artisan', turno_id=na_turno.id if na_turno else None)
                db_session.add(default_artisan)
                print("Usuario 'GCL1909' creado.")
            
        db_session.commit()
        print("Verificación de usuarios por defecto completada.")

    except Exception as e:
        db_session.rollback()
        print(f"ERROR al inicializar la base de datos: {e}", file=sys.stderr)
        raise

if __name__ == '__main__':
    print("="*60)
    print("--- Ejecutando script de inicialización de base de datos ---")
    print("="*60)
    init_db()
    create_default_admin()
    print("\n¡Proceso de inicialización completado exitosamente!")
    print("\n----------------------------------------------------------")
    print("Para ejecutar la aplicación web, utiliza el comando:")
    print(">>> python run.py")
    print("----------------------------------------------------------\n")