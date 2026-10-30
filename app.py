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
DATA_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)

SESSION_COOKIE = "archive_session"
SESSION_TTL = 60 * 60 * 24 * 7
MAX_PDF_BYTES = 20 * 1024 * 1024
SECRET_KEY = os.getenv("SECRET_KEY", "") or secrets.token_urlsafe(48)

app = FastAPI(title="EduSphere Question Paper Archive API", version="1.0.0")

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
        CREATE TABLE IF NOT EXISTS mock_tests (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          exam TEXT NOT NULL,
          subject TEXT NOT NULL,
          question TEXT NOT NULL,
          option_a TEXT NOT NULL,
          option_b TEXT NOT NULL,
          option_c TEXT NOT NULL,
          option_d TEXT NOT NULL,
          correct_option TEXT NOT NULL,
          explanation TEXT NOT NULL,
          official_source TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_papers_exam_year ON papers(exam, year DESC);
        """)
        
        # Default Admin Account
        email = os.getenv("ADMIN_EMAIL", "admin@edusphere.com").strip().lower()
        password = os.getenv("ADMIN_PASSWORD", "admin12345")
        if email and password and not db.execute("SELECT id FROM admins WHERE email=?", (email,)).fetchone():
            db.execute(
                "INSERT INTO admins(email,password_hash,is_admin,created_at) VALUES(?,?,1,?)",
                (email, hash_password(password), int(time.time()))
            )

        # Auto-Seed Official SQL Data if Table is Empty
        count = db.execute("SELECT COUNT(*) as c FROM papers").fetchone()["c"]
        if count == 0:
            db.executescript("""
            INSERT INTO papers (exam, year, subject, session, title, description, source_url, file_name, stored_name, file_size, downloads, created_at, updated_at) VALUES
            ('cbse-12', 2025, 'Physics', 'SQP 2024-25', 'CBSE Class 12 Physics Official Sample Question Paper', 'Official CBSE Class 12 Physics SQP.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Physics-SQP.pdf', 'Physics-SQP.pdf', 'EXTERNAL_URL', 1048576, 342, 1730000000, 1730000000),
            ('cbse-12', 2025, 'Physics', 'Solution Sheet', 'CBSE Class 12 Physics Official Marking Scheme & Solutions', 'Official CBSE Class 12 Physics Solutions.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Physics-MS.pdf', 'Physics-MS.pdf', 'EXTERNAL_URL', 1248576, 295, 1730000000, 1730000000),
            ('cbse-12', 2025, 'Mathematics', 'SQP 2024-25', 'CBSE Class 12 Mathematics Official Sample Question Paper', 'Official CBSE Class 12 Maths SQP.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Maths-SQP.pdf', 'Maths-SQP.pdf', 'EXTERNAL_URL', 1148576, 418, 1730000000, 1730000000),
            ('cbse-12', 2025, 'Mathematics', 'Solution Sheet', 'CBSE Class 12 Mathematics Official Solution Sheet', 'Official CBSE Class 12 Maths Solutions.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Maths-MS.pdf', 'Maths-MS.pdf', 'EXTERNAL_URL', 1348576, 360, 1730000000, 1730000000),
            ('cbse-12', 2025, 'Chemistry', 'SQP 2024-25', 'CBSE Class 12 Chemistry Official Sample Question Paper', 'Official CBSE Class 12 Chemistry SQP.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Chemistry-SQP.pdf', 'Chemistry-SQP.pdf', 'EXTERNAL_URL', 948576, 275, 1730000000, 1730000000),
            ('cbse-12', 2025, 'English Core', 'SQP 2024-25', 'CBSE Class 12 English Core Official Sample Paper', 'Official CBSE Class 12 English SQP.', 'https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/EnglishCore-SQP.pdf', 'EnglishCore-SQP.pdf', 'EXTERNAL_URL', 848576, 390, 1730000000, 1730000000),
            ('cbse-12', 2024, 'Physics', 'NCERT Book', 'NCERT Class 12 Physics Chapter 1 Textbook PDF', 'Official NCERT Physics Book.', 'https://ncert.nic.in/textbook/pdf/leph101.pdf', 'NCERT-Physics-Ch1.pdf', 'EXTERNAL_URL', 2548576, 540, 1730000000, 1730000000),
            ('cbse-12', 2024, 'Mathematics', 'NCERT Book', 'NCERT Class 12 Maths Chapter 1 Textbook PDF', 'Official NCERT Maths Book.', 'https://ncert.nic.in/textbook/pdf/lemh101.pdf', 'NCERT-Maths-Ch1.pdf', 'EXTERNAL_URL', 2148576, 515, 1730000000, 1730000000),
            ('cbse-10', 2025, 'Science', 'SQP 2024-25', 'CBSE Class 10 Science Official Sample Question Paper', 'Official CBSE Class 10 Science SQP.', 'https://cbseacademic.nic.in/web_material/SQP/ClassX_2024_25/Science-SQP.pdf', 'Class10-Science-SQP.pdf', 'EXTERNAL_URL', 1148576, 450, 1730000000, 1730000000),
            ('cbse-10', 2025, 'Mathematics', 'SQP 2024-25', 'CBSE Class 10 Mathematics Standard Sample Paper', 'Official CBSE Class 10 Maths SQP.', 'https://cbseacademic.nic.in/web_material/SQP/ClassX_2024_25/MathsStandard-SQP.pdf', 'Class10-Maths-SQP.pdf', 'EXTERNAL_URL', 1048576, 495, 1730000000, 1730000000),
            ('jee-advanced', 2024, 'Physics, Chemistry & Mathematics', 'Paper 1', 'JEE Advanced 2024 Official Question Paper 1', 'Official IIT JEE Advanced Paper 1.', 'https://jeeadv.ac.in/past_qps/2024_1_English.pdf', 'JEE-Adv-2024-P1.pdf', 'EXTERNAL_URL', 3148576, 620, 1730000000, 1730000000),
            ('jee-advanced', 2024, 'Physics, Chemistry & Mathematics', 'Paper 2', 'JEE Advanced 2024 Official Question Paper 2', 'Official IIT JEE Advanced Paper 2.', 'https://jeeadv.ac.in/past_qps/2024_2_English.pdf', 'JEE-Adv-2024-P2.pdf', 'EXTERNAL_URL', 3148576, 580, 1730000000, 1730000000),
            ('jee-main', 2025, 'Physics, Chemistry & Mathematics', 'Session 1', 'NTA JEE Main Official Sample Paper & Archive', 'Official NTA JEE Main Archive.', 'https://jeemain.nta.nic.in/', 'JEE-Main-2025.pdf', 'EXTERNAL_URL', 2548576, 780, 1730000000, 1730000000),
            ('neet', 2024, 'Physics, Chemistry & Biology', 'Main Exam', 'NTA NEET UG Official Question Paper Archive', 'Official NTA NEET UG Archive.', 'https://neet.nta.nic.in/', 'NEET-UG-2024.pdf', 'EXTERNAL_URL', 3548576, 890, 1730000000, 1730000000),
            ('isc-12', 2025, 'Physics', 'Specimen Paper', 'ISC Class 12 Physics Official Specimen Paper', 'Official CISCE ISC Class 12 Specimen.', 'https://cisce.org/specimen-question-papers-isc-class-xii-2025/', 'ISC-12-Physics.pdf', 'EXTERNAL_URL', 1048576, 185, 1730000000, 1730000000),
            ('icse-10', 2025, 'Physics', 'Specimen Paper', 'ICSE Class 10 Physics Official Specimen Paper', 'Official CISCE ICSE Class 10 Specimen.', 'https://cisce.org/specimen-question-papers-icse-class-x-2025/', 'ICSE-10-Physics.pdf', 'EXTERNAL_URL', 948576, 230, 1730000000, 1730000000);
            """)

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

@app.get("/")
def home():
    with connect() as db:
        total = db.execute("SELECT COUNT(*) n FROM papers").fetchone()["n"]
    return {"ok": True, "message": "EduSphere SQL Backend Running", "total_papers_in_sql": total}

@app.get("/api/health")
@app.get("/api/health/")
def health():
    return {"ok": True, "service": "question-paper-archive"}

@app.get("/api/session")
@app.get("/api/session/")
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

@app.get("/api/papers")
@app.get("/api/papers/")
def list_papers(exam: Optional[str] = None, q: Optional[str] = None, limit: int = 200, offset: int = 0):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    sql = "SELECT * FROM papers WHERE 1=1"
    args = []
    if exam:
        sql += " AND exam=?"; args.append(exam)
    if q:
        like = f"%{q.strip()}%"
        sql += " AND (title LIKE ? OR subject LIKE ? OR session LIKE ? OR CAST(year AS TEXT) LIKE ?)"
        args.extend([like, like, like, like])
    sql += " ORDER BY year DESC, id DESC LIMIT ? OFFSET ?"
    args.extend([limit, offset])
    with connect() as db:
        return [paper_dict(r) for r in db.execute(sql, args).fetchall()]

@app.get("/api/papers/{paper_id}")
@app.get("/api/papers/{paper_id}/")
def read_paper(paper_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Paper not found")
    return paper_dict(row)

@app.get("/api/papers/{paper_id}/file")
@app.get("/api/papers/{paper_id}/file/")
def paper_file(paper_id: int, download: int = 0):
    with connect() as db:
        row = db.execute("SELECT stored_name, file_name, source_url FROM papers WHERE id=?", (paper_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Paper not found")
        db.execute("UPDATE papers SET downloads=downloads+1, updated_at=? WHERE id=?", (int(time.time()), paper_id))
        if row["stored_name"] and row["stored_name"] != "EXTERNAL_URL":
            path = PDF_DIR / row["stored_name"]
            if path.exists():
                disposition = "attachment" if download else "inline"
                return FileResponse(path, media_type="application/pdf", filename=row["file_name"] or "paper.pdf", content_disposition_type=disposition)
        if row["source_url"]:
            return RedirectResponse(url=row["source_url"])
    raise HTTPException(404, "PDF not found")

@app.get("/api/stats")
@app.get("/api/stats/")
@app.get("/api/admin/stats")
@app.get("/api/admin/stats/")
def stats():
    with connect() as db:
        rows = db.execute("""
          SELECT exam, COUNT(*) total,
          SUM(CASE WHEN (stored_name<>'' OR source_url<>'') THEN 1 ELSE 0 END) withFile
          FROM papers GROUP BY exam
        """).fetchall()
    return [{"exam": r["exam"], "total": r["total"], "withFile": r["withFile"]} for r in rows]

@app.get("/api/dashboard")
@app.get("/api/dashboard/")
@app.get("/api/admin/dashboard")
@app.get("/api/admin/dashboard/")
def dashboard():
    with connect() as db:
        total = db.execute("SELECT COUNT(*) n FROM papers").fetchone()["n"]
        with_file = db.execute("SELECT COUNT(*) n FROM papers WHERE (stored_name<>'' OR source_url<>'')").fetchone()["n"]
        downloads = db.execute("SELECT COALESCE(SUM(downloads),0) n FROM papers").fetchone()["n"]
    return {"total": total, "withFile": with_file, "downloads": downloads}

@app.get("/api/mock-tests")
@app.get("/api/mock-tests/")
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
@app.post("/api/admin/papers/")
async def create_paper(request: Request):
    require_admin(request)
    form = await request.form()
    fields = parse_paper_fields(form.get("exam"), form.get("year"), form.get("subject"),
                                form.get("session"), form.get("title"), form.get("description"), form.get("sourceUrl"))
    filename = stored = ""; size = 0
    upload = form.get("file")
    if upload and getattr(upload, "filename", ""):
        filename, stored, size = save_pdf(upload)
    elif fields[6]:
        stored = "EXTERNAL_URL"
    now = int(time.time())
    with connect() as db:
        cur = db.execute("""INSERT INTO papers
          (exam,year,subject,session,title,description,source_url,file_name,stored_name,file_size,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (*fields, filename, stored, size, now, now))
        item = get_paper(db, cur.lastrowid)
    return item

@app.put("/api/admin/papers/{paper_id}")
@app.put("/api/admin/papers/{paper_id}/")
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
@app.delete("/api/admin/papers/{paper_id}/")
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
