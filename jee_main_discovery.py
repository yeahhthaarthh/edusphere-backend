
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from datetime import datetime
from collections import deque


# ==================================================
# CONFIGURATION
# ==================================================

BASE_URL = "https://jeemain.nta.nic.in/"
SITEMAP_URL = urljoin(BASE_URL, "sitemap/")

FIRST_YEAR = 2014
LAST_YEAR = 2026

MAX_PAGES = 60
MAX_DEPTH = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 EduSphere JEE Main Discovery"
}

ALLOWED_HOSTS = {
    "jeemain.nta.nic.in",
    "nta.ac.in",
    "www.nta.ac.in",
    "cdnbbsr.s3waas.gov.in",
}

SEED_PAGES = [
    BASE_URL,
    SITEMAP_URL,
    urljoin(BASE_URL, "archive/"),
    urljoin(BASE_URL, "documents/"),
    urljoin(BASE_URL, "question-paper/"),
]


# ==================================================
# BASIC HELPERS
# ==================================================

def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def canonical_url(url):
    url, _ = urldefrag(url)
    return url.strip()


def is_official_url(url):
    parsed = urlparse(url)

    if parsed.scheme != "https":
        return False

    host = parsed.netloc.lower()

    return (
        host in ALLOWED_HOSTS
        or host.endswith(".nta.ac.in")
        or host.endswith(".s3waas.gov.in")
    )


def get_page(url):
    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30
    )
    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser"
    )


def is_pdf_url(url):
    return urlparse(url).path.lower().endswith(".pdf")


def is_relevant_page(url):
    path = urlparse(url).path.lower()

    keywords = (
        "archive",
        "document",
        "question",
        "paper",
        "sitemap",
        "download",
        "notice",
    )

    return any(word in path for word in keywords)


# ==================================================
# EXTRACT YEAR
# Only use visible title and page context.
# Do not use the PDF URL because its date may
# represent upload date rather than exam year.
# ==================================================

def extract_year(text):
    match = re.search(
        r"\b(201[4-9]|202[0-6])\b",
        text or ""
    )

    return int(match.group(1)) if match else None


# ==================================================
# EXTRACT PAPER TYPE
# ==================================================

def identify_paper_type(text):
    text = (text or "").lower()

    if re.search(r"\bb\.?\s*planning\b", text):
        return "Paper 2B"

    if re.search(r"\bb\.?\s*arch\b", text):
        return "Paper 2A"

    if re.search(r"\bpaper\s*2b\b", text):
        return "Paper 2B"

    if re.search(r"\bpaper\s*2a\b", text):
        return "Paper 2A"

    if (
        re.search(r"\bb\.?\s*tech\b", text)
        or re.search(r"\bb\.?\s*e\.?\s*/?\s*b\.?\s*tech\b", text)
        or re.search(r"\bpaper\s*1\b", text)
    ):
        return "Paper 1"

    return None


# ==================================================
# DOCUMENT TYPE
# Only accept actual Question Paper documents.
# Answer Keys and solutions are excluded.
# ==================================================

def identify_document_type(text):
    text = (text or "").lower()

    excluded_terms = (
        "answer key",
        "answer-key",
        "final answer",
        "provisional answer",
        "response sheet",
        "recorded response",
        "question paper with answer",
        "solution",
        "solutions",
    )

    if any(term in text for term in excluded_terms):
        return None

    question_paper_terms = (
        "question paper",
        "question-paper",
        "questionpaper",
    )

    if any(term in text for term in question_paper_terms):
        if identify_paper_type(text):
            return "Question Paper"

    return None


# ==================================================
# EXTRACT EXAM DATE
# ==================================================

def extract_exam_date(text):
    months = (
        "January|February|March|April|May|June|"
        "July|August|September|October|November|December"
    )

    patterns = [
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({months})\s+(20\d{{2}})\b",
        rf"\b({months})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(20\d{{2}})\b",
    ]

    match = re.search(patterns[0], text or "", re.I)

    if match:
        day, month, year = match.groups()
    else:
        match = re.search(patterns[1], text or "", re.I)

        if not match:
            return ""

        month, day, year = match.groups()

    try:
        parsed = datetime.strptime(
            f"{day} {month} {year}",
            "%d %B %Y"
        )
        return parsed.strftime("%Y-%m-%d")

    except ValueError:
        return ""


# ==================================================
# EXTRACT SESSION
# ==================================================

def extract_session(text):
    text = (text or "").lower()

    if re.search(r"session[\s_-]*1\b", text):
        return "Session 1"

    if re.search(r"session[\s_-]*2\b", text):
        return "Session 2"

    if re.search(r"\b(january|jan|february|feb)\b", text):
        return "Session 1"

    if re.search(r"\b(march|mar|april|apr)\b", text):
        return "Session 2"

    return "Not specified"


# ==================================================
# EXTRACT SHIFT
# ==================================================

def extract_shift(text):
    match = re.search(
        r"\bshift\s*[-:]?\s*([12])\b",
        text or "",
        re.I
    )

    return f"Shift {match.group(1)}" if match else ""


# ==================================================
# EXTRACT LANGUAGE
# ==================================================

def extract_language(text):
    languages = [
        "English", "Hindi", "Assamese", "Bengali",
        "Gujarati", "Kannada", "Malayalam", "Marathi",
        "Odia", "Punjabi", "Tamil", "Telugu", "Urdu"
    ]

    text = (text or "").lower()

    for language in languages:
        if re.search(
            rf"\b{re.escape(language.lower())}\b",
            text
        ):
            return language

    return "Not specified"


# ==================================================
# BUILD PAPER RECORD
# ==================================================

def make_record(title, context, pdf_url, source_page):
    visible_text = clean_text(f"{title} {context}")

    if not is_official_url(pdf_url):
        return None

    if not is_pdf_url(pdf_url):
        return None

    # Never use PDF URL text to determine exam year.
    year = extract_year(visible_text)

    if not year:
        return None

    paper_type = identify_paper_type(visible_text)

    if not paper_type:
        return None

    document_type = identify_document_type(visible_text)

    if document_type != "Question Paper":
        return None

    lower_text = visible_text.lower()

    # Require a clear JEE Main reference.
    if (
        "jee main" not in lower_text
        and "jeemain" not in lower_text
    ):
        return None

    exam_date = extract_exam_date(visible_text)
    session = extract_session(visible_text)
    shift = extract_shift(visible_text)
    language = extract_language(visible_text)

    date_label = exam_date or "Date not specified"
    shift_label = shift or "Shift not specified"

    record_title = (
        f"JEE Main {year} | {session} | "
        f"{date_label} | {shift_label} | "
        f"{paper_type} | Question Paper"
    )

    return {
        "year": year,
        "session_name": session,
        "exam_date": exam_date,
        "shift": shift,
        "paper_type": paper_type,
        "language": language,
        "document_type": "Question Paper",
        "title": record_title,
        "source_url": pdf_url,
        "source_page": source_page,
        "source_authority": "NTA",
        "verification_status": "official_link",
        "source_type": "direct_pdf",
        "source_label": "Official NTA PDF"
    }


# ==================================================
# DISCOVER PAGES AND PDF LINKS
# ==================================================

def discover_official_papers():
    discovered = {}
    visited = set()

    queue = deque()

    for page in SEED_PAGES:
        if is_official_url(page):
            queue.append((canonical_url(page), 0))

    while queue and len(visited) < MAX_PAGES:
        page_url, depth = queue.popleft()
        page_url = canonical_url(page_url)

        if page_url in visited:
            continue

        visited.add(page_url)

        try:
            soup = get_page(page_url)
        except requests.RequestException:
            continue

        for link in soup.find_all("a", href=True):
            href = link.get("href", "").strip()

            if not href:
                continue

            target_url = canonical_url(
                urljoin(page_url, href)
            )

            if not is_official_url(target_url):
                continue

            title = clean_text(
                link.get_text(" ", strip=True)
            )

            # Use only the nearest parent context.
            # Do not collect several ancestor levels,
            # as that can mix unrelated documents.
            parent = link.parent

            parent_context = ""

            if parent is not None:
                parent_context = clean_text(
                    parent.get_text(" ", strip=True)
                )

            context = clean_text(
                f"{title} {parent_context}"
            )

            if is_pdf_url(target_url):
                record = make_record(
                    title,
                    context,
                    target_url,
                    page_url
                )

                if record:
                    discovered[target_url] = record

                continue

            if (
                depth < MAX_DEPTH
                and target_url not in visited
                and is_relevant_page(target_url)
            ):
                queue.append(
                    (target_url, depth + 1)
                )

    return list(discovered.values())


# ==================================================
# YEAR-LEVEL FALLBACKS
# These are portal links, NOT individual papers.
# ==================================================

def discover_year_fallbacks(papers):
    years_with_papers = {
        paper["year"] for paper in papers
    }

    fallbacks = []

    for year in range(FIRST_YEAR, LAST_YEAR + 1):
        if year in years_with_papers:
            continue

        fallbacks.append({
            "year": year,
            "source_url": BASE_URL,
            "source_type": "official_page",
            "source_label": (
                f"NTA portal only - "
                f"{year} year-specific archive not verified"
            ),
            "source_authority": "NTA",
            "verification_status": "portal_only"
        })

    return fallbacks


# ==================================================
# DISCOVERY TEST
# ==================================================

def discover_jee_main_papers():
    return discover_official_papers()


# ==================================================
# DATABASE SYNC
# ==================================================

def sync_jee_main_papers():
    from app import connect

    papers = discover_official_papers()
    fallbacks = discover_year_fallbacks(papers)

    added = 0
    skipped = 0

    fallback_added = 0
    fallback_skipped = 0

    now = int(time.time())

    with connect() as db:

        for paper in papers:
            existing = db.execute(
                """
                SELECT id
                FROM jee_main_papers
                WHERE source_url = %s
                """,
                (paper["source_url"],)
            ).fetchone()

            if existing:
                skipped += 1
                continue

            db.execute(
                """
                INSERT INTO jee_main_papers (
                    year, session_name, exam_date, shift,
                    paper_type, language, document_type,
                    title, source_url, source_page,
                    source_authority, verification_status,
                    source_type, source_label,
                    created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    paper["year"],
                    paper["session_name"],
                    paper["exam_date"],
                    paper["shift"],
                    paper["paper_type"],
                    paper["language"],
                    paper["document_type"],
                    paper["title"],
                    paper["source_url"],
                    paper["source_page"],
                    paper["source_authority"],
                    paper["verification_status"],
                    paper["source_type"],
                    paper["source_label"],
                    now,
                    now
                )
            )

            added += 1

        for fallback in fallbacks:
            existing = db.execute(
                """
                SELECT id
                FROM jee_main_year_sources
                WHERE year = %s
                  AND source_url = %s
                """,
                (
                    fallback["year"],
                    fallback["source_url"]
                )
            ).fetchone()

            if existing:
                fallback_skipped += 1
                continue

            db.execute(
                """
                INSERT INTO jee_main_year_sources (
                    year, source_url, source_type,
                    source_label, source_authority,
                    verification_status, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    fallback["year"],
                    fallback["source_url"],
                    fallback["source_type"],
                    fallback["source_label"],
                    fallback["source_authority"],
                    fallback["verification_status"],
                    now,
                    now
                )
            )

            fallback_added += 1

    return {
        "success": True,
        "direct_papers_discovered": len(papers),
        "direct_papers_added": added,
        "direct_papers_skipped": skipped,
        "year_fallbacks_discovered": len(fallbacks),
        "year_fallbacks_added": fallback_added,
        "year_fallbacks_skipped": fallback_skipped
    }
