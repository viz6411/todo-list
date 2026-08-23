"""WSGI entry point for Flask auto-detection."""
from server import create_app

app = create_app()
