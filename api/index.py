import sys
import os

# Add root directory to sys.path so backend imports work properly in Vercel serverless environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app

# Export app for Vercel WSGI
application = app
