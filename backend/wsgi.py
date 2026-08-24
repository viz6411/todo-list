"""WSGI entry point for Flask auto-detection."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
from server import create_app

app = create_app()
