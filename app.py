import hmac
import os
import re
import secrets
import sqlite3
import time
import uuid
from functools import wraps
from urllib.parse import urlparse

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get('DATABASE_PATH', os.path.join(BASE_DIR, 'movies.db'))
MEDIA_DIR = os.path.join(BASE_DIR, 'static', 'media')
UPLOAD_SUBDIR = 'uploads'

POSTER_EXTS = {'jpg', 'jpeg', 'png', 'webp', 'avif', 'gif'}
VIDEO_EXTS = {'mp4', 'webm'}

SCHEMA = '''
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        year TEXT NOT NULL,
        description TEXT,
        poster TEXT,
        video TEXT
    )
'''

app = Flask(__name__)

# --- CONFIG (all secrets come from environment variables) -------------------
app.config.update(
    SECRET_KEY=os.environ.get('SECRET_KEY') or secrets.token_hex(32),
    MAX_CONTENT_LENGTH=int(os.environ.get('MAX_UPLOAD_MB', '300')) * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE') == '1',
)
if not os.environ.get('SECRET_KEY'):
    print('WARNING: SECRET_KEY is not set. Using a random key; admin logins '
          'will reset on every restart and break with multiple workers.')
if os.environ.get('TRUST_PROXY') == '1':  # set on Render / Heroku / behind nginx
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


# --- DATABASE ---------------------------------------------------------------
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_schema():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(SCHEMA)


init_schema()  # the app can start on a brand-new server with no setup step


# --- MEDIA HELPERS ----------------------------------------------------------
def is_url(value):
    parts = urlparse(value)
    return parts.scheme in ('http', 'https') and bool(parts.netloc)


def local_media_path(name):
    """Absolute path of a file inside static/media, or None if it escapes it."""
    root = os.path.realpath(MEDIA_DIR)
    path = os.path.realpath(os.path.join(root, name))
    return path if path.startswith(root + os.sep) else None


def local_media_exists(name):
    path = local_media_path(name)
    return bool(path and os.path.isfile(path))


@app.template_filter('media_url')
def media_url(value):
    """DB value -> browser URL. Full URLs pass through, filenames live in static/media."""
    if not value:
        return ''
    if is_url(value):
        return value
    return url_for('static', filename='media/' + value.lstrip('/'))


@app.template_filter('video_mime')
def video_mime(value):
    return 'video/webm' if (value or '').lower().split('?')[0].endswith('.webm') else 'video/mp4'


def check_media(field, allowed_exts, label):
    """Validate a poster/video field. Returns (db_value, upload_or_None, error_or_None).
    Nothing is written to disk here, so a failed form never leaves orphan files."""
    upload = request.files.get(field + '_file')
    text = request.form.get(field, '').strip()
    if upload and upload.filename:
        ext = upload.filename.rsplit('.', 1)[-1].lower() if '.' in upload.filename else ''
        if ext not in allowed_exts:
            return None, None, f'{label}: allowed file types are {", ".join(sorted(allowed_exts))}.'
        return None, upload, None
    if not text:
        return None, None, f'{label} is required (upload a file or enter a filename / URL).'
    if is_url(text) or local_media_exists(text):
        return text, None, None
    return None, None, f'{label}: "{text}" was not found in static/media/ and is not a valid http(s) URL.'


def store_upload(upload):
    ext = upload.filename.rsplit('.', 1)[-1].lower()
    name = secure_filename(upload.filename) or f'file.{ext}'
    if not name.lower().endswith('.' + ext):
        name += '.' + ext
    rel = f'{UPLOAD_SUBDIR}/{uuid.uuid4().hex[:8]}_{name}'
    dest = local_media_path(rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    upload.save(dest)
    return rel


def delete_uploaded(value):
    """Only ever deletes files the admin form itself uploaded."""
    if value and value.startswith(UPLOAD_SUBDIR + '/'):
        path = local_media_path(value)
        if path and os.path.isfile(path):
            os.remove(path)


def validate_movie_form():
    title = request.form.get('title', '').strip()
    year = request.form.get('year', '').strip()
    description = request.form.get('description', '').strip()
    errors = []
    if not title or len(title) > 120:
        errors.append('Title is required (max 120 characters).')
    if not re.fullmatch(r'\d{4}', year):
        errors.append('Year must be 4 digits, e.g. 2008.')
    if len(description) > 500:
        errors.append('Description must be 500 characters or fewer.')
    poster, poster_up, e1 = check_media('poster', POSTER_EXTS, 'Poster')
    video, video_up, e2 = check_media('video', VIDEO_EXTS, 'Video')
    errors += [e for e in (e1, e2) if e]
    return dict(title=title, year=year, description=description,
                poster=poster, poster_up=poster_up,
                video=video, video_up=video_up), errors


# --- SECURITY: CSRF, LOGIN, HEADERS ------------------------------------------
def csrf_token():
    if '_csrf' not in session:
        session['_csrf'] = secrets.token_urlsafe(32)
    return session['_csrf']


app.jinja_env.globals['csrf_token'] = csrf_token


@app.before_request
def csrf_protect():
    if request.method == 'POST':
        expected = session.get('_csrf', '')
        sent = request.form.get('_csrf', '')
        if not expected or not hmac.compare_digest(expected, sent):
            abort(400, 'Your session expired. Please reload the page and try again.')


@app.after_request
def security_headers(resp):
    resp.headers.setdefault('X-Content-Type-Options', 'nosniff')
    resp.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
    resp.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    if request.endpoint != 'static' and (session.get('admin') or request.path in ('/login',)):
        resp.headers['Cache-Control'] = 'no-store'
    return resp


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get('admin'):
            return redirect(url_for('login', next=request.path))
        return view(*args, **kwargs)
    return wrapper


_attempts = {}  # ip -> [timestamps]; simple brute-force guard (per worker)


def too_many_attempts(ip):
    now = time.time()
    recent = [t for t in _attempts.get(ip, []) if now - t < 300]
    _attempts[ip] = recent
    return len(recent) >= 5


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('admin'):
        return redirect(url_for('admin'))
    if request.method == 'POST':
        ip = request.remote_addr or 'unknown'
        password = os.environ.get('ADMIN_PASSWORD', '')
        if not password:
            flash('Admin login is disabled: the ADMIN_PASSWORD environment variable is not set.', 'error')
        elif too_many_attempts(ip):
            flash('Too many attempts. Please wait a few minutes.', 'error')
        elif hmac.compare_digest(request.form.get('password', '').encode(), password.encode()):
            session.clear()
            session['admin'] = True
            nxt = request.args.get('next', '')
            if not (nxt.startswith('/') and not nxt.startswith('//')):
                nxt = url_for('admin')
            return redirect(nxt)
        else:
            _attempts.setdefault(ip, []).append(time.time())
            flash('Incorrect password.', 'error')
    return render_template('login.html')


@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('home'))


# --- PUBLIC SITE -------------------------------------------------------------
@app.route('/')
def home():
    movies = get_db().execute('SELECT * FROM movies ORDER BY id DESC').fetchall()
    return render_template('index.html', movies=movies)


# --- ADMIN (all routes below require login) ---------------------------------
def render_admin(form=None, status=200):
    movies = get_db().execute('SELECT * FROM movies ORDER BY id DESC').fetchall()
    return render_template('admin.html', movies=movies, form=form or {}), status


@app.route('/admin')
@login_required
def admin():
    return render_admin()


@app.route('/sales_dashboard')
@login_required
def sales_dashboard():
    return render_template('sales_dashboard.html')


@app.route('/add_movie', methods=['POST'])
@login_required
def add_movie():
    data, errors = validate_movie_form()
    if errors:
        for e in errors:
            flash(e, 'error')
        return render_admin(form=request.form, status=400)
    poster = data['poster'] or store_upload(data['poster_up'])
    video = data['video'] or store_upload(data['video_up'])
    db = get_db()
    db.execute('INSERT INTO movies (title, year, description, poster, video) VALUES (?, ?, ?, ?, ?)',
               (data['title'], data['year'], data['description'], poster, video))
    db.commit()
    flash(f'Added "{data["title"]}".', 'ok')
    return redirect(url_for('admin'))


@app.route('/delete_movie/<int:movie_id>', methods=['POST'])
@login_required
def delete_movie(movie_id):
    db = get_db()
    movie = db.execute('SELECT * FROM movies WHERE id = ?', (movie_id,)).fetchone()
    if movie is None:
        abort(404)
    db.execute('DELETE FROM movies WHERE id = ?', (movie_id,))
    db.commit()
    delete_uploaded(movie['poster'])
    delete_uploaded(movie['video'])
    flash(f'Deleted "{movie["title"]}".', 'ok')
    return redirect(url_for('admin'))


def get_movie_or_404(movie_id):
    movie = get_db().execute('SELECT * FROM movies WHERE id = ?', (movie_id,)).fetchone()
    if movie is None:
        abort(404)
    return movie


@app.route('/edit_movie/<int:movie_id>')
@login_required
def edit_movie(movie_id):
    return render_template('edit.html', movie=get_movie_or_404(movie_id), form={})


@app.route('/update_movie/<int:movie_id>', methods=['POST'])
@login_required
def update_movie(movie_id):
    movie = get_movie_or_404(movie_id)
    data, errors = validate_movie_form()
    if errors:
        for e in errors:
            flash(e, 'error')
        return render_template('edit.html', movie=movie, form=request.form), 400
    poster = data['poster'] or store_upload(data['poster_up'])
    video = data['video'] or store_upload(data['video_up'])
    db = get_db()
    db.execute('''UPDATE movies SET title = ?, year = ?, description = ?, poster = ?, video = ?
                  WHERE id = ?''',
               (data['title'], data['year'], data['description'], poster, video, movie_id))
    db.commit()
    if movie['poster'] != poster:
        delete_uploaded(movie['poster'])
    if movie['video'] != video:
        delete_uploaded(movie['video'])
    flash(f'Saved "{data["title"]}".', 'ok')
    return redirect(url_for('admin'))


# --- ERRORS ------------------------------------------------------------------
@app.errorhandler(404)
def not_found(_e):
    return render_template('error.html', code=404, message='That page could not be found.'), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template('error.html', code=400, message=getattr(e, 'description', 'Bad request.')), 400


@app.errorhandler(413)
def too_large(_e):
    return render_template('error.html', code=413,
                           message='That file is too large. Use a smaller file or paste a hosted video URL instead.'), 413


if __name__ == '__main__':
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
