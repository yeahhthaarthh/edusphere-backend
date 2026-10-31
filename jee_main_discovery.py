
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
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
        "answer",
    )

    return any(word in path for word in keywords)


# ==================================================
# EXTRACT YEAR
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

    if (
        re.search(r"\bb\.?\s*tech\b", text)
        or re.search(r"\bb\.?\s*e\.?\s*/?\s*b\.?\s*tech\b", text)
        or "paper 1" in text
    ):
        return "Paper 1"

    return None


# ==================================================
# DOCUMENT TYPE
# ==================================================

def identify_document_type(text):
    text = (text or "").lower()

    if "answer key" in text or "answer-key" in text:
        return "Answer Key"

    if (
        identify_paper_type(text)
        and (
            "question paper" in text
            or "question-paper" in text
            or "b.tech" in text
            or "b.e." in text
            or "b.arch" in text
            or "b.planning" in text
            or "paper 1" in text
            or "paper 2" in text
        )
    ):
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
    combined = clean_text(f"{title} {context} {pdf_url}")

    if not is_official_url(pdf_url):
        return None

    if not is_pdf_url(pdf_url):
        return None

    year = extract_year(combined)

    if not year:
        return None

    paper_type = identify_paper_type(combined)

    if not paper_type:
        return None

    document_type = identify_document_type(combined)

    if not document_type:
        return None

    # Avoid treating unrelated NTA notices as question papers.
    if "jee main" not in combined.lower() and "jeemain" not in combined.lower():
        if "b.tech" not in combined.lower() and "b.e." not in combined.lower():
            return None

    exam_date = extract_exam_date(combined)
    session = extract_session(combined)
    shift = extract_shift(combined)
    language = extract_language(combined)

    date_label = exam_date or "Date not specified"
    shift_label = shift or "Shift not specified"

    record_title = (
        f"JEE Main {year} | {session} | "
        f"{date_label} | {shift_label} | "
        f"{paper_type} | {document_type}"
    )

    return {
        "year": year,
        "session_name": session,
        "exam_date": exam_date,
        "shift": shift,
        "paper_type": paper_type,
        "language": language,
        "document_type": document_type,
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
            queue.append((page, 0))

    while queue and len(visited) < MAX_PAGES:
        page_url, depth = queue.popleft()

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

            target_url = urljoin(page_url, href)

            if not is_official_url(target_url):
                continue

            title = clean_text(
                link.get_text(" ", strip=True)
            )

            parent = link.parent

            context_parts = [title]

            for _ in range(3):
                if parent is None:
                    break

                context_parts.append(
                    parent.get_text(" ", strip=True)
                )
                parent = parent.parent

            context = clean_text(" ".join(context_parts))

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
                queue.append((target_url, depth + 1))

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
                f"Official NTA portal - "
                f"check JEE Main {year} archive"
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
