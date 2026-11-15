# OpenStream

Flask movie site: public catalogue + password-protected admin (add / edit / delete / upload) and a sales dashboard.

## Run locally

```powershell
python -m venv venv
venv\Scripts\activate            # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python init_db.py                # creates movies.db + starter movies (safe to re-run)

# Windows PowerShell                          # macOS/Linux
$env:SECRET_KEY="any-long-random-string"      # export SECRET_KEY=...
$env:ADMIN_PASSWORD="choose-a-password"       # export ADMIN_PASSWORD=...
python app.py
```
Site: http://127.0.0.1:5000  -  Admin: http://127.0.0.1:5000/login

## Deploy (Render, Railway, etc.)
- Start command: `gunicorn app:app --workers 2 --timeout 120` (see `Procfile`)
- Environment variables: see `.env.example` (`SECRET_KEY`, `ADMIN_PASSWORD`, `SESSION_COOKIE_SECURE=1`, `TRUST_PROXY=1`)
- Run `python init_db.py` once after the first deploy.
- **Storage:** most free hosts wipe the disk on every redeploy. Attach a persistent disk and set `DATABASE_PATH`
  (and keep uploads on it), or host videos on object storage / a CDN and paste the URL in the admin form.

## Media
Files live in `static/media/`. In the admin form give a filename from that folder, a full https:// URL, or upload a file.
Only publish public-domain, Creative Commons or your own films.
