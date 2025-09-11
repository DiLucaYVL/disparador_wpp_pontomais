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
    app.run(use_reloader=False, host="0.0.0.0", port=8000)