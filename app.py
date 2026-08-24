"""Flask application entry point for auto-detection."""
import os
import sys

# Add backend directory to path so Flask can import the app
_backend_dir = os.path.join(os.path.dirname(__file__), 'backend')
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from server import create_app

app = create_app()
