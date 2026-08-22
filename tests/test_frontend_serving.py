"""Tests for the frontend index route serving."""
import pytest
import sys
import os
import tempfile
import shutil

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


@pytest.fixture
def app():
    """Create a fresh test app with empty storage."""
    tmpdir = tempfile.mkdtemp()
    storage_path = os.path.join(tmpdir, 'todos.json')
    from server import create_app
    app = create_app(storage_path)
    app.config['TESTING'] = True
    yield app
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_index_route_serves_html(app):
    """GET / should serve the frontend index.html."""
    client = app.test_client()
    resp = client.get('/')
    assert resp.status_code == 200
    assert resp.content_type.startswith('text/html')
    assert b'Todo List' in resp.data


def test_static_files_served(app):
    """Static CSS/JS files should be accessible."""
    client = app.test_client()

    # CSS
    css_resp = client.get('/static/css/style.css')
    assert css_resp.status_code == 200
    assert css_resp.content_type == 'text/css; charset=utf-8'

    # JS
    js_resp = client.get('/static/js/app.js')
    assert js_resp.status_code == 200
    assert js_resp.content_type == 'text/javascript; charset=utf-8'


def test_index_html_references_static_files(app):
    """index.html should reference our CSS and JS files."""
    client = app.test_client()
    resp = client.get('/')
    html = resp.data.decode('utf-8')
    assert '/static/css/style.css' in html
    assert '/static/js/app.js' in html
