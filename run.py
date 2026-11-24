"""
Entry point to run the AI Image Caption Generator Application.
"""
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app import app

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    print("=" * 65)
    print(" 🌟 AI Image Caption Generator (AWS Rekognition & Bedrock) 🌟")
    print(f" Serving web app at: http://localhost:{port}")
    print("=" * 65)
    app.run(host='0.0.0.0', port=port, debug=False)
