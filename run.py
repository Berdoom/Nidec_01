import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug_mode = not os.getenv('RENDER')
    print("="*50)
    print(">>> INICIANDO SERVIDOR FLASK DE NIDEC <<<")
    print(f">>> Escuchando en: http://127.0.0.1:{port}")
    print(f">>> Modo Debug: {'ACTIVADO' if debug_mode else 'DESACTIVADO'}")
    print("="*50)
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)