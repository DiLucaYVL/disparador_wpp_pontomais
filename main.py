from flask import Flask, render_template, jsonify, send_from_directory
from app.routes import api_bp
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.register_blueprint(api_bp)


@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    os.environ['FLASK_RUN_FROM_CLI'] = 'false'  # força execução única
    
    # Verifica se deve usar debug mode
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1' or os.getenv('FLASK_ENV') == 'development'
    
    print(f"🐛 Debug mode: {debug_mode}")
    print(f"🌐 Servidor iniciando em http://127.0.0.1:5000")
    
    app.run(debug=debug_mode, use_reloader=False, host='127.0.0.1', port=5000)