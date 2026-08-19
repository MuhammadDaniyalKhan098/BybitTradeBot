import os
from threading import Thread
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Service Active"

@app.route('/health')
def health():
    return {"status": "healthy"}

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

def keep_alive():
    server_thread = Thread(target=run_server, daemon=True)
    server_thread.start()