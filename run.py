"""
Single-command local launcher for Lumina Vision Studio.
Serves root static assets locally while Vercel uses api/index.py + CDN directly.
"""
import os
import sys
from flask import send_from_directory

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, ROOT_DIR)

from api.index import app

@app.route('/')
def local_index():
    return send_from_directory(ROOT_DIR, 'index.html')

@app.route('/<path:filename>')
def local_static(filename):
    if filename.startswith('api/'):
        return {"error": "Not found"}, 404
    return send_from_directory(ROOT_DIR, filename)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print("=" * 60)
    print(" Lumina Vision Studio")
    print(f" Live server: http://localhost:{port}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False)
