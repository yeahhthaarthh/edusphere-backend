import os, sqlite3, secrets, hashlib, hmac, time, re
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Request, Response, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", APP_DIR / "data"))
PDF_DIR = DATA_DIR / "papers"
DB_PATH = DATA_DIR / "archive.sqlite3"
SEED_SQL_PATH = APP_DIR / "seed_data.sql"

DATA_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

SESSION_COOKIE = "archive_session"
SESSION_TTL = 60 * 60 * 24 * 7
MAX_PDF_BYTES = 20 * 1024 * 1024
SECRET_KEY = os.getenv("SECRET_KEY", "") or secrets.token_urlsafe(48)

app = FastAPI(title="EduSphere Question Paper Archive API", version="1.0.0")

# Allow CORS for Netlify frontend and local testing
cors_origins_env = os.getenv("CORS_ORIGINS", "https://souray.netlify.app,http://localhost:3000,http://127.0.0.1:3000")
allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.netlify\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

def connect():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db

def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    derived = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return salt.hex() + "$" + derived.hex()

def verify_password(password: str, encoded: str) -> bool:
    try:
        salt_hex, hash_hex = encoded.split("$", 1)
        candidate = hash_password(password, bytes.fromhex(salt_hex)).split("$", 1)[1]
        return hmac.compare_digest(candidate, hash_hex)
    except (ValueError, TypeError):
        return False

def init_db():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS admins (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          email TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          is_admin INTEGER NOT NULL DEFAULT 1,
          created_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY,
          admin_id INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
          expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS papers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          exam TEXT NOT NULL,
          year INTEGER NOT NULL,
          subject TEXT NOT NULL,
          session TEXT NOT NULL DEFAULT '',
          title TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          source_url TEXT NOT NULL DEFAULT '',
          file_name TEXT NOT NULL DEFAULT '',
          stored_name TEXT NOT NULL DEFAULT '',
          file_size INTEGER NOT NULL DEFAULT 0,
          downloads INTEGER NOT NULL DEFAULT 0,
          created_at INTEGER NOT NULL,
          updated_at INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_papers_exam_year ON papers(exam, year DESC);
        """)
        
        # 1. Create Default Admin Account
        email = os.getenv("ADMIN_EMAIL", "admin@edusphere.com").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "admin12345")
        if email and password and not db.execute("SELECT id FROM admins WHERE email=?", (email,)).fetchone():
            db.execute(
                "INSERT INTO admins(email,password_hash,is_admin,created_at) VALUES(?,?,1,?)",
                (email, hash_password(password), int(time.time()))
            )

        # 2. Automatically Seed Official SQL Data if 'papers' table is empty
        paper_count = db.execute("SELECT COUNT(*) as cnt FROM papers").fetchone()["cnt"]
        if paper_count == 0 and SEED_SQL_PATH.exists():
            sql_script = SEED_SQL_PATH.read_text(encoding="utf-8")
            db.executescript(sql_script)
            print("Successfully seeded SQLite database with official CBSE, ICSE, NCERT & NTA papers!")

init_db()

def clean_email(value: str) -> str:
    return value.strip().lower()

def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def current_admin(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    now = int(time.time())
    with connect() as db:
        row = db.execute("""
          SELECT a.id, a.email, a.is_admin FROM sessions s
          JOIN admins a ON a.id=s.admin_id
          WHERE s.token_hash=? AND s.expires_at>?
        """, (token_hash(token), now)).fetchone()
        if row:
            return dict(row)
    return None

def require_admin(request: Request):
    admin = current_admin(request)
    if not admin or not admin["is_admin"]:
        raise HTTPException(status_code=401, detail="Admin sign-in required")
    return admin

def paper_dict(row):
    item = dict(row)
    item["hasFile"] = bool(item.get("stored_name") or item.get("source_url"))
    item["sourceUrl"] = item.pop("source_url", "")
    item["fileSize"] = item.pop("file_size", 0)
    item["fileName"] = item.pop("file_name", "")
    item.pop("stored_name", None)
    item.pop("created_at", None)
    item.pop("updated_at", None)
    return item

def get_paper(db, paper_id: int):
    row = db.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
    return paper_dict(row) if row else None

def parse_paper_fields(exam, year, subject, session, title, description, source_url):
    exam = (exam or "").strip()
    subject = (subject or "").strip()
    title = (title or "").strip()
    source_url = (source_url or "").strip()
    if not re.fullmatch(r"[a-z0-9-]{1,60}", exam):
        raise HTTPException(400, "Invalid exam slug")
    if not 1990 <= int(year) <= 2100:
        raise HTTPException(400, "Year must be between 1990 and 2100")
    if not subject or len(subject) > 100:
        raise HTTPException(400, "Subject is required (max 100 characters)")
    if len(title) < 3 or len(title) > 240:
        raise HTTPException(400, "Title must be between 3 and 240 characters")
    if source_url and not (source_url.startswith("https://") or source_url.startswith("http://")):
        raise HTTPException(400, "Source URL must start with http:// or https://")
    return (exam, int(year), subject, (session or "").strip()[:120], title,
            (description or "").strip()[:2000], source_url[:1000])

def save_pdf(upload: UploadFile):
    filename = Path(upload.filename or "paper.pdf").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")
    data = upload.file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF must be 20 MB or smaller")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(400, "The uploaded file does not appear to be a valid PDF")
    stored = secrets.token_hex(16) + ".pdf"
    (PDF_DIR / stored).write_bytes(data)
    return filename, stored, len(data)

@app.get("/")
def root_status():
    with connect() as db:
        count = db.execute("SELECT COUNT(*) as n FROM papers").fetchone()["n"]
    return {
        "ok": True,
        "service": "EduSphere Python + SQL Backend is Running!",
        "papers_in_sql_database": count,
        "test_links": {
            "health": "/api/health",
            "all_papers": "/api/papers",
            "exam_stats": "/api/stats",
            "mock_tests": "/api/mock-tests",
            "interactive_docs": "/docs"
        }
    }

@app.get("/api/health")
def health():
    return {"ok": True, "service": "question-paper-archive"}

@app.get("/api/session")
def session_info(request: Request):
    admin = current_admin(request)
    return {"session": {"email": admin["email"], "isAdmin": bool(admin["is_admin"])} if admin else None}

@app.post("/api/auth/login")
async def login(request: Request, response: Response):
    body = await request.json()
    email = clean_email(str(body.get("email", "")))
    password = str(body.get("password", ""))
    with connect() as db:
        row = db.execute("SELECT * FROM admins WHERE email=?", (email,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            raise HTTPException(401, "Invalid email or password")
        token = secrets.token_urlsafe(40)
        expires = int(time.time()) + SESSION_TTL
        db.execute("INSERT INTO sessions(token_hash,admin_id,expires_at) VALUES(?,?,?)",
                   (token_hash(token), row["id"], expires))
    secure_cookie = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, secure=secure_cookie,
        samesite="none" if secure_cookie else "lax", max_age=SESSION_TTL, path="/"
    )
    return {"session": {"email": row["email"], "isAdmin": bool(row["is_admin"])}}

@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash(token),))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}

@app.post("/api/auth/forgot-password")
async def forgot_password(request: Request):
    body = await request.json()
    email = clean_email(str(body.get("email", "")))
    return {"ok": True, "message": "If an account exists, password reset instructions can be sent."}

@app.get("/api/papers")
def list_papers(
    exam: Optional[str] = None,
    year: Optional[int] = None,
    subject: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 200,
    offset: int = 0
):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    sql = "SELECT * FROM papers WHERE 1=1"
    args = []
    if exam:
        sql += " AND exam=?"
        args.append(exam)
    if year:
        sql += " AND year=?"
        args.append(year)
    if subject:
        sql += " AND subject=?"
        args.append(subject)
    if q:
        like = f"%{q.strip()}%"
        sql += " AND (title LIKE ? OR subject LIKE ? OR session LIKE ? OR CAST(year AS TEXT) LIKE ?)"
        args.extend([like, like, like, like])
    sql += " ORDER BY year DESC, id DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    with connect() as db:
        return [paper_dict(r) for r in db.execute(sql, args).fetchall()]

@app.get("/api/papers/{paper_id}")
def read_paper(paper_id: int):
    with connect() as db:
        item = get_paper(db, paper_id)
    if not item:
        raise HTTPException(404, "Paper not found")
    return item

@app.get("/api/papers/{paper_id}/file")
def paper_file(paper_id: int, request: Request, download: int = 0):
    with connect() as db:
        row = db.execute("SELECT stored_name, file_name, source_url FROM papers WHERE id=?", (paper_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Paper not found")
        
        # Increment SQL download counter
        db.execute("UPDATE papers SET downloads=downloads+1, updated_at=? WHERE id=?", (int(time.time()), paper_id))
        
        # If it is a local uploaded PDF and exists on disk, serve it
        if row["stored_name"] and row["stored_name"] != "EXTERNAL_URL":
            path = PDF_DIR / row["stored_name"]
            if path.exists():
                disposition = "attachment" if download else "inline"
                return FileResponse(path, media_type="application/pdf", filename=row["file_name"] or "paper.pdf",
                                    content_disposition_type=disposition)
        
        # Otherwise redirect to the official CBSE / NCERT / NTA / CISCE URL stored in SQL
        if row["source_url"]:
            return RedirectResponse(url=row["source_url"])
            
        raise HTTPException(404, "PDF file not found")

@app.get("/api/stats")
@app.get("/api/admin/stats")
def stats():
    with connect() as db:
        rows = db.execute("""
          SELECT exam, COUNT(*) total,
          SUM(CASE WHEN (stored_name<>'' OR source_url<>'') THEN 1 ELSE 0 END) withFile
          FROM papers GROUP BY exam
        """).fetchall()
    return [{"exam": r["exam"], "total": r["total"], "withFile": r["withFile"]} for r in rows]

@app.get("/api/dashboard")
@app.get("/api/admin/dashboard")
def dashboard():
    with connect() as db:
        total = db.execute("SELECT COUNT(*) n FROM papers").fetchone()["n"]
        with_file = db.execute("SELECT COUNT(*) n FROM papers WHERE (stored_name<>'' OR source_url<>'')").fetchone()["n"]
        downloads = db.execute("SELECT COALESCE(SUM(downloads),0) n FROM papers").fetchone()["n"]
    return {"total": total, "withFile": with_file, "downloads": downloads}

@app.get("/api/mock-tests")
def list_mock_tests(exam: Optional[str] = None, subject: Optional[str] = None):
    sql = "SELECT * FROM mock_tests WHERE 1=1"
    args = []
    if exam:
        sql += " AND exam=?"
        args.append(exam)
    if subject:
        sql += " AND subject=?"
        args.append(subject)
    with connect() as db:
        return [dict(r) for r in db.execute(sql, args).fetchall()]

@app.post("/api/admin/papers")
async def create_paper(request: Request):
    require_admin(request)
    form = await request.form()
    fields = parse_paper_fields(form.get("exam"), form.get("year"), form.get("subject"),
                                form.get("session"), form.get("title"), form.get("description"), form.get("sourceUrl"))
    filename = stored = ""; size = 0
    upload = form.get("file")
    if upload and getattr(upload, "filename", ""):
        filename, stored, size = save_pdf(upload)
    elif fields[6]:  # If sourceUrl is provided without file upload, mark as EXTERNAL_URL
        stored = "EXTERNAL_URL"
    now = int(time.time())
    with connect() as db:
        cur = db.execute("""INSERT INTO papers
          (exam,year,subject,session,title,description,source_url,file_name,stored_name,file_size,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (*fields, filename, stored, size, now, now))
        item = get_paper(db, cur.lastrowid)
    return item

@app.put("/api/admin/papers/{paper_id}")
async def update_paper(paper_id: int, request: Request):
    require_admin(request)
    form = await request.form()
    fields = parse_paper_fields(form.get("exam"), form.get("year"), form.get("subject"),
                                form.get("session"), form.get("title"), form.get("description"), form.get("sourceUrl"))
    with connect() as db:
        old = db.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
        if not old:
            raise HTTPException(404, "Paper not found")
        filename, stored, size = old["file_name"], old["stored_name"], old["file_size"]
        upload = form.get("file")
        if upload and getattr(upload, "filename", ""):
            filename, stored, size = save_pdf(upload)
        remove_file = str(form.get("removeFile", "")).lower() == "true"
        if remove_file:
            filename, stored, size = "", "", 0
        db.execute("""UPDATE papers SET exam=?,year=?,subject=?,session=?,title=?,description=?,source_url=?,
          file_name=?,stored_name=?,file_size=?,updated_at=? WHERE id=?""",
          (*fields, filename, stored, size, int(time.time()), paper_id))
        return get_paper(db, paper_id)

@app.delete("/api/admin/papers/{paper_id}")
def delete_paper(paper_id: int, request: Request):
    require_admin(request)
    with connect() as db:
        row = db.execute("SELECT stored_name FROM papers WHERE id=?", (paper_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Paper not found")
        db.execute("DELETE FROM papers WHERE id=?", (paper_id,))
    return {"ok": True}

@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail, "detail": exc.detail})
