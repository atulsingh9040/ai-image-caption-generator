"""
Local launcher for AI Caption Studio.
Imports unified Flask application from api.index.
"""
import os
import sys

# Ensure current directory is on sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from api.index import app

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print("=" * 60)
    print(" 🌟 Lumina Vision Studio (AI Image Caption & Scene Analysis)")
    print(f" Web application running at: http://localhost:{port}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=True)
