"""
Local development server for Lumina Vision Studio.
Run locally:
    pip install -r api/requirements.txt
    python run.py
"""
import os
import sys


def start_local_server():
    from flask import send_from_directory

    root_dir = os.path.abspath(os.path.dirname(__file__))
    sys.path.insert(0, root_dir)

    from api.index import app as flask_app

    @flask_app.route('/')
    def local_index():
        return send_from_directory(root_dir, 'index.html')

    @flask_app.route('/<path:filename>')
    def local_static(filename):
        if filename.startswith('api/'):
            return {"error": "Not found"}, 404
        return send_from_directory(root_dir, filename)

    port = int(os.getenv('PORT', 5000))
    print("=" * 60)
    print(" Lumina Vision Studio (Local Dev)")
    print(f" Live server: http://localhost:{port}")
    print("=" * 60)
    flask_app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    start_local_server()
