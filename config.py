import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'n1D3c$#pro'
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    if not DATABASE_URL:
        if os.getenv('RENDER'):
            raise ValueError("FATAL ERROR: La variable de entorno DATABASE_URL no está definida en el entorno de Render.")
        else:
            print("ADVERTENCIA: DATABASE_URL no encontrada. Usando SQLite local.")
            project_root = os.path.dirname(os.path.abspath(__file__))
            instance_path = os.path.join(project_root, 'instance')
            os.makedirs(instance_path, exist_ok=True)
            db_path = os.path.join(instance_path, 'produccion.db')
            DATABASE_URL = f'sqlite:///{db_path}'
            
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False