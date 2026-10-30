import os
import re
import time
import uuid
import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from supabase import create_client
from fastapi import FastAPI, Request, Response, HTTPException, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware

# ---------- Configuration ----------
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_SERVICE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    or os.getenv("SUPABASE_SECRET_KEY", "").strip()
)
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "edusphere-papers").strip()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing from the backend environment.")

SESSION_COOKIE = "archive_session"
SESSION_TTL = 60 * 60 * 24 * 7
MAX_PDF_BYTES = 50 * 1024 * 1024
_storage = None

app = FastAPI(title="EduSphere Question Paper Archive API", version="2.0.0")

cors_env = os.getenv(
    "CORS_ORIGINS",
    "https://souray.netlify.app,http://localhost:3000,http://127.0.0.1:3000",
)
allowed_origins = [x.strip() for x in cors_env.split(",") if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.netlify\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# ---------- PostgreSQL / Supabase Storage ----------
def connect():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def storage():
    global _storage
    if _storage is None:
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            raise RuntimeError(
                "Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the backend environment."
            )
        _storage = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    return _storage


def save_pdf(upload: UploadFile):
    if not upload or not upload.filename:
        raise HTTPException(400, "Choose a PDF file first")

    original_name = Path(upload.filename).name
    if not original_name.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are allowed")

    try:
        upload.file.seek(0)
        content = upload.file.read(MAX_PDF_BYTES + 1)
        upload.file.seek(0)
    except Exception:
        raise HTTPException(400, "Could not read the uploaded file")

    if not content:
        raise HTTPException(400, "The uploaded PDF is empty")
    if len(content) > MAX_PDF_BYTES:
        raise HTTPException(413, "PDF must be 50 MB or smaller")
    if b"%PDF-" not in content[:1024]:
        raise HTTPException(400, "The uploaded file does not appear to be a valid PDF")

    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "-", original_name).strip(".-") or "paper.pdf"
    object_path = f"{uuid.uuid4().hex}-{safe_name}"

    try:
        storage().storage.from_(SUPABASE_BUCKET).upload(
            object_path,
            content,
            file_options={
                "content-type": "application/pdf",
                "cache-control": "3600",
                "upsert": "false",
            },
        )
    except Exception as exc:
        raise HTTPException(502, f"PDF storage upload failed: {str(exc)[:250]}")

    return original_name, object_path, len(content)


def public_pdf_url(object_path: str):
    try:
        return storage().storage.from_(SUPABASE_BUCKET).get_public_url(object_path)
    except Exception as exc:
        raise HTTPException(502, f"Could not create PDF link: {str(exc)[:200]}")


def delete_stored_pdf(object_path: str):
    if not object_path or object_path == "EXTERNAL_URL":
        return
    try:
        storage().storage.from_(SUPABASE_BUCKET).remove([object_path])
    except Exception:
        # A failed cleanup does not undo a successful database deletion.
        pass


# ---------- Authentication ----------
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


def clean_email(value: str) -> str:
    return value.strip().lower()


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_admin(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    with connect() as db:
        row = db.execute(
            """SELECT a.id, a.email, a.is_admin
               FROM sessions s JOIN admins a ON a.id = s.admin_id
               WHERE s.token_hash = %s AND s.expires_at > %s""",
            (token_hash(token), int(time.time())),
        ).fetchone()
    return dict(row) if row else None


def require_admin(request: Request):
    admin = current_admin(request)
    if not admin or not admin["is_admin"]:
        raise HTTPException(401, "Admin sign-in required")
    return admin


# ---------- Database initialization ----------
def init_db():
    email = clean_email(os.getenv("ADMIN_EMAIL", "admin@edusphere.com"))
    password = os.getenv("ADMIN_PASSWORD", "")
    with connect() as db:
        existing = db.execute("SELECT id FROM admins WHERE email = %s", (email,)).fetchone()
        if not existing:
            if not password:
                raise RuntimeError(
                    "Set a strong ADMIN_PASSWORD in the backend environment before startup."
                )
            db.execute(
                """INSERT INTO admins(email, password_hash, is_admin, created_at)
                   VALUES (%s, %s, TRUE, %s) ON CONFLICT (email) DO NOTHING""",
                (email, hash_password(password), int(time.time())),
            )

        count = db.execute("SELECT COUNT(*) AS c FROM papers").fetchone()["c"]
        if count == 0:
            now = int(time.time())
            seed_rows = [
                ("cbse-12", 2025, "Physics", "SQP 2024-25", "CBSE Class 12 Physics Official Sample Question Paper", "Official CBSE Class 12 Physics SQP.", "https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Physics-SQP.pdf", "Physics-SQP.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("cbse-12", 2025, "Physics", "Solution Sheet", "CBSE Class 12 Physics Official Marking Scheme & Solutions", "Official CBSE Class 12 Physics solutions.", "https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Physics-MS.pdf", "Physics-MS.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("cbse-12", 2025, "Mathematics", "SQP 2024-25", "CBSE Class 12 Mathematics Official Sample Question Paper", "Official CBSE Class 12 Maths SQP.", "https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Maths-SQP.pdf", "Maths-SQP.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("cbse-12", 2025, "Mathematics", "Solution Sheet", "CBSE Class 12 Mathematics Official Solution Sheet", "Official CBSE Class 12 Maths solutions.", "https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Maths-MS.pdf", "Maths-MS.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("cbse-12", 2025, "Chemistry", "SQP 2024-25", "CBSE Class 12 Chemistry Official Sample Question Paper", "Official CBSE Class 12 Chemistry SQP.", "https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/Chemistry-SQP.pdf", "Chemistry-SQP.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("cbse-12", 2025, "English Core", "SQP 2024-25", "CBSE Class 12 English Core Official Sample Paper", "Official CBSE Class 12 English SQP.", "https://cbseacademic.nic.in/web_material/SQP/ClassXII_2024_25/EnglishCore-SQP.pdf", "EnglishCore-SQP.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("cbse-12", 2024, "Physics", "NCERT Book", "NCERT Class 12 Physics Chapter 1 Textbook PDF", "Official NCERT Physics book.", "https://ncert.nic.in/textbook/pdf/leph101.pdf", "NCERT-Physics-Ch1.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("cbse-12", 2024, "Mathematics", "NCERT Book", "NCERT Class 12 Maths Chapter 1 Textbook PDF", "Official NCERT Maths book.", "https://ncert.nic.in/textbook/pdf/lemh101.pdf", "NCERT-Maths-Ch1.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("cbse-10", 2025, "Science", "SQP 2024-25", "CBSE Class 10 Science Official Sample Question Paper", "Official CBSE Class 10 Science SQP.", "https://cbseacademic.nic.in/web_material/SQP/ClassX_2024_25/Science-SQP.pdf", "Class10-Science-SQP.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("cbse-10", 2025, "Mathematics", "SQP 2024-25", "CBSE Class 10 Mathematics Standard Sample Paper", "Official CBSE Class 10 Maths SQP.", "https://cbseacademic.nic.in/web_material/SQP/ClassX_2024_25/MathsStandard-SQP.pdf", "Class10-Maths-SQP.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("jee-advanced", 2024, "Physics, Chemistry & Mathematics", "Paper 1", "JEE Advanced 2024 Official Question Paper 1", "Official IIT JEE Advanced Paper 1.", "https://jeeadv.ac.in/past_qps/2024_1_English.pdf", "JEE-Adv-2024-P1.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("jee-advanced", 2024, "Physics, Chemistry & Mathematics", "Paper 2", "JEE Advanced 2024 Official Question Paper 2", "Official IIT JEE Advanced Paper 2.", "https://jeeadv.ac.in/past_qps/2024_2_English.pdf", "JEE-Adv-2024-P2.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("jee-main", 2025, "Physics, Chemistry & Mathematics", "Session 1", "JEE Main Official Question Paper Archive", "Official NTA JEE Main archive.", "https://jeemain.nta.nic.in/", "JEE-Main-2025.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("neet", 2024, "Physics, Chemistry & Biology", "Main Exam", "NTA NEET UG Official Question Paper Archive", "Official NTA NEET UG archive.", "https://neet.nta.nic.in/", "NEET-UG-2024.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("isc-12", 2025, "Physics", "Specimen Paper", "ISC Class 12 Physics Official Specimen Paper", "Official CISCE ISC Class 12 specimen.", "https://cisce.org/specimen-question-papers-isc-class-xii-2025/", "ISC-12-Physics.pdf", "EXTERNAL_URL", 0, 0, now, now),
                ("icse-10", 2025, "Physics", "Specimen Paper", "ICSE Class 10 Physics Official Specimen Paper", "Official CISCE ICSE Class 10 specimen.", "https://cisce.org/specimen-question-papers-icse-class-x-2025/", "ICSE-10-Physics.pdf", "EXTERNAL_URL", 0, 0, now, now),
            ]
            db.executemany(
                """INSERT INTO papers
                   (exam, year, subject, session, title, description, source_url,
                    file_name, stored_name, file_size, downloads, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                seed_rows,
            )


# ---------- Paper helpers ----------
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
    row = db.execute("SELECT * FROM papers WHERE id = %s", (paper_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Paper not found")
    return paper_dict(row)


def parse_paper_fields(exam, year, subject, session, title, description, source_url):
    exam = (exam or "").strip()
    subject = (subject or "").strip()
    title = (title or "").strip()
    source_url = (source_url or "").strip()
    try:
        year = int(year)
    except (TypeError, ValueError):
        raise HTTPException(400, "A valid year is required")
    if not re.fullmatch(r"[a-z0-9-]{1,60}", exam):
        raise HTTPException(400, "Invalid exam slug")
    if not 1990 <= year <= 2100:
        raise HTTPException(400, "Year must be between 1990 and 2100")
    if not subject or len(subject) > 100:
        raise HTTPException(400, "Subject is required (max 100 characters)")
    if len(title) < 3 or len(title) > 240:
        raise HTTPException(400, "Title must be between 3 and 240 characters")
    if source_url and not (source_url.startswith("https://") or source_url.startswith("http://")):
        raise HTTPException(400, "Source URL must start with http:// or https://")
    return (
        exam, year, subject, (session or "").strip()[:120], title,
        (description or "").strip()[:2000], source_url[:1000],
    )


# ---------- Startup ----------
init_db()


# ---------- Public API ----------
@app.get("/")
def home():
    with connect() as db:
        total = db.execute("SELECT COUNT(*) AS n FROM papers").fetchone()["n"]
    return {"ok": True, "message": "EduSphere PostgreSQL Backend Running", "total_papers_in_sql": total}


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
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")
    email = clean_email(str(body.get("email", "")))
    password = str(body.get("password", ""))
    with connect() as db:
        row = db.execute("SELECT * FROM admins WHERE email = %s", (email,)).fetchone()
        if not row or not verify_password(password, row["password_hash"]):
            raise HTTPException(401, "Invalid email or password")
        token = secrets.token_urlsafe(40)
        expires = int(time.time()) + SESSION_TTL
        db.execute(
            "INSERT INTO sessions(token_hash, admin_id, expires_at) VALUES (%s, %s, %s)",
            (token_hash(token), row["id"], expires),
        )
    secure = os.getenv("COOKIE_SECURE", "true").lower() == "true"
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, secure=secure,
        samesite="none" if secure else "lax", max_age=SESSION_TTL, path="/",
    )
    return {"session": {"email": row["email"], "isAdmin": bool(row["is_admin"])}}


@app.post("/api/auth/logout")
def logout(request: Request, response: Response):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash = %s", (token_hash(token),))
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
        sql += " AND exam = %s"
        args.append(exam)
    if q:
        like = f"%{q.strip()}%"
        sql += " AND (title ILIKE %s OR subject ILIKE %s OR session ILIKE %s OR CAST(year AS TEXT) ILIKE %s)"
        args.extend([like, like, like, like])
    sql += " ORDER BY year DESC, id DESC LIMIT %s OFFSET %s"
    args.extend([limit, offset])
    with connect() as db:
        rows = db.execute(sql, args).fetchall()
    return [paper_dict(row) for row in rows]


@app.get("/api/papers/{paper_id}")
@app.get("/api/papers/{paper_id}/")
def read_paper(paper_id: int):
    with connect() as db:
        row = db.execute("SELECT * FROM papers WHERE id = %s", (paper_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Paper not found")
    return paper_dict(row)


@app.get("/api/papers/{paper_id}/file")
@app.get("/api/papers/{paper_id}/file/")
def paper_file(paper_id: int, download: int = 0):
    with connect() as db:
        row = db.execute(
            "SELECT stored_name, file_name, source_url FROM papers WHERE id = %s",
            (paper_id,),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Paper not found")
        db.execute(
            "UPDATE papers SET downloads = downloads + 1, updated_at = %s WHERE id = %s",
            (int(time.time()), paper_id),
        )
    if row["stored_name"] and row["stored_name"] != "EXTERNAL_URL":
        return RedirectResponse(public_pdf_url(row["stored_name"]), status_code=302)
    if row["source_url"]:
        return RedirectResponse(row["source_url"], status_code=302)
    raise HTTPException(404, "PDF not found")


@app.get("/api/stats")
@app.get("/api/stats/")
@app.get("/api/admin/stats")
@app.get("/api/admin/stats/")
def stats():
    with connect() as db:
        rows = db.execute(
            """SELECT exam, COUNT(*) AS total,
               SUM(CASE WHEN (stored_name <> '' OR source_url <> '') THEN 1 ELSE 0 END) AS "withFile"
               FROM papers GROUP BY exam"""
        ).fetchall()
    return [{"exam": r["exam"], "total": r["total"], "withFile": r["withFile"]} for r in rows]


@app.get("/api/dashboard")
@app.get("/api/dashboard/")
@app.get("/api/admin/dashboard")
@app.get("/api/admin/dashboard/")
def dashboard():
    with connect() as db:
        total = db.execute("SELECT COUNT(*) AS n FROM papers").fetchone()["n"]
        with_file = db.execute(
            "SELECT COUNT(*) AS n FROM papers WHERE (stored_name <> '' OR source_url <> '')"
        ).fetchone()["n"]
        downloads = db.execute("SELECT COALESCE(SUM(downloads), 0) AS n FROM papers").fetchone()["n"]
    return {"total": total, "withFile": with_file, "downloads": downloads}


@app.get("/api/mock-tests")
@app.get("/api/mock-tests/")
def list_mock_tests(exam: Optional[str] = None, subject: Optional[str] = None):
    sql = "SELECT * FROM mock_tests WHERE 1=1"
    args = []
    if exam:
        sql += " AND exam = %s"
        args.append(exam)
    if subject:
        sql += " AND subject = %s"
        args.append(subject)
    with connect() as db:
        rows = db.execute(sql, args).fetchall()
    return [dict(r) for r in rows]


# ---------- Admin paper management ----------
@app.post("/api/admin/papers")
@app.post("/api/admin/papers/")
async def create_paper(request: Request):
    require_admin(request)
    form = await request.form()
    fields = parse_paper_fields(
        form.get("exam"), form.get("year"), form.get("subject"), form.get("session"),
        form.get("title"), form.get("description"), form.get("sourceUrl"),
    )
    filename, stored, size = "", "", 0
    upload = form.get("file")
    if upload and getattr(upload, "filename", ""):
        filename, stored, size = save_pdf(upload)
    elif fields[6]:
        stored = "EXTERNAL_URL"
    now = int(time.time())
    with connect() as db:
        row = db.execute(
            """INSERT INTO papers
               (exam, year, subject, session, title, description, source_url,
                file_name, stored_name, file_size, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (*fields, filename, stored, size, now, now),
        ).fetchone()
        result = get_paper(db, row["id"])
    return result


@app.put("/api/admin/papers/{paper_id}")
@app.put("/api/admin/papers/{paper_id}/")
async def update_paper(paper_id: int, request: Request):
    require_admin(request)
    form = await request.form()
    fields = parse_paper_fields(
        form.get("exam"), form.get("year"), form.get("subject"), form.get("session"),
        form.get("title"), form.get("description"), form.get("sourceUrl"),
    )
    old_path = ""
    replacement_path = ""
    with connect() as db:
        old = db.execute("SELECT * FROM papers WHERE id = %s", (paper_id,)).fetchone()
        if not old:
            raise HTTPException(404, "Paper not found")
        filename, stored, size = old["file_name"], old["stored_name"], old["file_size"]
        old_path = stored if stored and stored != "EXTERNAL_URL" else ""
        upload = form.get("file")
        if upload and getattr(upload, "filename", ""):
            filename, stored, size = save_pdf(upload)
            replacement_path = stored
        if str(form.get("removeFile", "")).lower() == "true":
            filename, stored, size = "", "", 0
            replacement_path = ""
        db.execute(
            """UPDATE papers SET exam=%s, year=%s, subject=%s, session=%s, title=%s,
               description=%s, source_url=%s, file_name=%s, stored_name=%s,
               file_size=%s, updated_at=%s WHERE id=%s""",
            (*fields, filename, stored, size, int(time.time()), paper_id),
        )
        result = get_paper(db, paper_id)
    if old_path and old_path != replacement_path:
        delete_stored_pdf(old_path)
    return result


@app.delete("/api/admin/papers/{paper_id}")
@app.delete("/api/admin/papers/{paper_id}/")
def delete_paper(paper_id: int, request: Request):
    require_admin(request)
    with connect() as db:
        row = db.execute("SELECT stored_name FROM papers WHERE id = %s", (paper_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Paper not found")
        stored_path = row["stored_name"]
        db.execute("DELETE FROM papers WHERE id = %s", (paper_id,))
    delete_stored_pdf(stored_path)
    return {"ok": True}


# ---------- Error handling ----------
@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "detail": exc.detail},
    )
