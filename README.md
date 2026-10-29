Python backend conversion
This project supplies a Python/FastAPI backend for the uploaded question-paper archive frontend.
What is included
SQLite database for papers, admin accounts and sessions.
Admin sign-in and sign-out with HttpOnly session cookies.
Public paper listing and PDF view/download endpoints.
Admin dashboard metrics and exam coverage stats.
Admin create/edit/delete paper endpoints.
PDF validation and upload limit of 20 MB.
Passwords stored using Python's scrypt hash, not plaintext.
Run locally
Python 3.10+ recommended.
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
Set environment variables before starting:
ADMIN_EMAIL — initial administrator email
ADMIN_PASSWORD — initial administrator password
SECRET_KEY — long random secret (set this in production)
COOKIE_SECURE=true when serving over HTTPS
DATA_DIR — persistent directory for SQLite database and PDFs
CORS_ORIGINS — comma-separated frontend origins
Then run:
uvicorn app:app --host 0.0.0.0 --port 8000
Interactive API docs: /docs.
API routes
GET /api/health
GET /api/session
POST /api/auth/login JSON { "email": "...", "password": "..." }
POST /api/auth/logout
POST /api/auth/forgot-password (placeholder response only; email delivery is not configured)
GET /api/papers
GET /api/papers/{id}
GET /api/papers/{id}/file and ?download=1
GET /api/admin/dashboard (admin)
GET /api/admin/stats (admin)
POST /api/admin/papers multipart form
PUT /api/admin/papers/{id} multipart form
DELETE /api/admin/papers/{id} (admin)
Important integration note
The uploaded files are built/minified frontend JavaScript chunks, not the original server source. The frontend appears to use TanStack Start server functions for loading papers, authentication, statistics, and mutations. This backend cannot replace those opaque server-function calls automatically.
To complete the conversion, update the frontend's server-function wrappers to call these /api/... routes (using fetch with credentials: "include"), and configure the frontend to use the backend origin. The existing PDF links already use /api/papers/{id}/file.
For production, deploy the Python service and frontend with a persistent disk for DATA_DIR; otherwise SQLite and uploaded PDFs may be lost on redeploy. Use HTTPS and set COOKIE_SECURE=true.
