"""WSGI entry point for Docker containers.

Reads environment variables and routes to the appropriate storage backend:
- STORAGE_BACKEND=json  → JSONFileBackend (file-based, default)
- STORAGE_BACKEND=sheets → GoogleSheetsBackend (requires credentials)

Environment variables are validated BEFORE the app is created, so the
container exits with a clear error message instead of crashing silently.
"""
import logging
import os
import sys

# Configure logging early so startup messages are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Environment validation — fail fast with actionable diagnostics
# ------------------------------------------------------------------

STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "json").lower().strip()

if STORAGE_BACKEND == "json":
    logger.info("Storage backend: JSON (file-based)")
elif STORAGE_BACKEND == "sheets":
    # Google Sheets requires at least one auth method
    has_oauth = bool(os.environ.get("OAUTH_CREDENTIALS"))
    has_sa_file = bool(os.environ.get("SERVICE_ACCOUNT_FILE"))
    has_sa_creds = bool(os.environ.get("SERVICE_ACCOUNT_CREDENTIALS"))

    if not (has_oauth or has_sa_file or has_sa_creds):
        logger.error(
            "STORAGE_BACKEND=sheets requires authentication credentials.\n"
            "Set one of these environment variables:\n"
            "  OAUTH_CREDENTIALS          - path to OAuth2 token JSON file\n"
            "  SERVICE_ACCOUNT_FILE       - path to service account JSON key\n"
            "  SERVICE_ACCOUNT_CREDENTIALS - service account JSON content\n\n"
            "Or set STORAGE_BACKEND=json for file-based storage."
        )
        sys.exit(1)
    else:
        logger.info("Storage backend: Google Sheets (auth detected)")
else:
    logger.error(
        "STORAGE_BACKEND='%s' is not recognized. Use 'json' or 'sheets'.",
        STORAGE_BACKEND,
    )
    sys.exit(1)

# ------------------------------------------------------------------
# Build backend kwargs from environment
# ------------------------------------------------------------------

backend_kwargs = {}

if STORAGE_BACKEND == "sheets":
    backend_kwargs["backend_type"] = "sheets"
    backend_kwargs["spreadsheet_id"] = os.environ.get("SPREADSHEET_ID", "")
    backend_kwargs["sheet_name"] = os.environ.get("SHEET_NAME", "Todos")

    oauth = os.environ.get("OAUTH_CREDENTIALS")
    if oauth:
        backend_kwargs["oauth_credentials"] = oauth

    sa_file = os.environ.get("SERVICE_ACCOUNT_FILE")
    if sa_file:
        backend_kwargs["service_account_file"] = sa_file

    sa_creds = os.environ.get("SERVICE_ACCOUNT_CREDENTIALS")
    if sa_creds:
        backend_kwargs["service_account_credentials"] = sa_creds
else:
    backend_kwargs["backend_type"] = "json"
    backend_kwargs["storage_path"] = os.environ.get(
        "STORAGE_PATH", "/data/todos.json"
    )

# ------------------------------------------------------------------
# Create app
# ------------------------------------------------------------------

from backend.server import create_app

app = create_app(**backend_kwargs)

# ------------------------------------------------------------------
# Gunicorn entry point
# ------------------------------------------------------------------

application = app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
