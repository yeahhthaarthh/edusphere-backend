
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime


# ==================================================
# CONFIGURATION
# ==================================================

BASE_URL = "https://jeemain.nta.nic.in/"
SITEMAP_URL = urljoin(BASE_URL, "sitemap/")

FIRST_YEAR = 2014
LAST_YEAR = 2026

HEADERS = {
    "User-Agent": "Mozilla/5.0 EduSphere JEE Main Discovery"
}

ALLOWED_HOSTS = {
    "jeemain.nta.nic.in",
    "nta.ac.in",
    "www.nta.ac.in",
    "cdnbbsr.s3waas.gov.in",
}


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
        timeout=40
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser"
    )


# ==================================================
# EXTRACT YEAR
# ==================================================

def extract_year(text):
    match = re.search(
        r"\b(201[4-9]|202[0-6])\b",
        text
    )

    return int(match.group(1)) if match else None


# ==================================================
# EXTRACT PAPER TYPE
# ==================================================

def identify_paper_type(text):
    text = text.lower()

    if re.search(r"\bb\.?\s*planning\b", text):
        return "Paper 2B"

    if re.search(r"\bb\.?\s*arch\b", text):
        return "Paper 2A"

    if (
        re.search(r"\bb\.?\s*tech\b", text)
        or re.search(r"\bb\.?\s*e\.?\b", text)
    ):
        return "Paper 1"

    return None


# ==================================================
# EXTRACT DOCUMENT TYPE
# ==================================================

def identify_document_type(text):
    text = text.lower()

    if "answer key" in text or "answer-key" in text:
        return "Answer Key"

    if identify_paper_type(text):
        return "Question Paper"

    return None


# ==================================================
# EXTRACT DATE
# Supports:
# 2nd Apr 2026
# 2 April 2026
# April 2, 2026
# ==================================================

def extract_exam_date(text):

    months = (
        "January|February|March|April|May|June|"
        "July|August|September|October|November|December"
    )

    pattern_one = (
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+"
        rf"({months})\s+(20\d{{2}})\b"
    )

    pattern_two = (
        rf"\b({months})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+"
        rf"(20\d{{2}})\b"
    )

    match = re.search(pattern_one, text, re.I)

    if match:
        day, month, year = match.groups()

    else:
        match = re.search(pattern_two, text, re.I)

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

    text = text.lower()

    if re.search(r"session[\s_-]*1\b", text):
        return "Session 1"

    if re.search(r"session[\s_-]*2\b", text):
        return "Session 2"

    # January / February = Session 1
    if re.search(r"\b(january|jan|february|feb)\b", text):
        return "Session 1"

    # March / April = Session 2
    if re.search(r"\b(march|mar|april|apr)\b", text):
        return "Session 2"

    return "Not specified"


# ==================================================
# EXTRACT SHIFT
# ==================================================

def extract_shift(text):

    match = re.search(
        r"\bshift\s*[-:]?\s*([12])\b",
        text,
        re.I
    )

    if match:
        return f"Shift {match.group(1)}"

    return ""


# ==================================================
# EXTRACT LANGUAGE
# ==================================================

def extract_language(text):

    languages = [
        "English",
        "Hindi",
        "Assamese",
        "Bengali",
        "Gujarati",
        "Kannada",
        "Malayalam",
        "Marathi",
        "Odia",
        "Punjabi",
        "Tamil",
        "Telugu",
        "Urdu"
    ]

    lower_text = text.lower()

    for language in languages:
        if re.search(
            rf"\b{re.escape(language.lower())}\b",
            lower_text
        ):
            return language

    return "Not specified"


# ==================================================
# CREATE INDIVIDUAL PAPER RECORD
# ==================================================

def make_record(title, context, pdf_url, source_page):

    combined_text = clean_text(
        f"{title} {context}"
    )

    year = extract_year(combined_text)

    if not year:
        return None

    paper_type = identify_paper_type(combined_text)

    if not paper_type:
        return None

    document_type = identify_document_type(combined_text)

    if not document_type:
        return None

    exam_date = extract_exam_date(combined_text)
    session = extract_session(combined_text)
    shift = extract_shift(combined_text)
    language = extract_language(combined_text)

    if not pdf_url.lower().split("?")[0].endswith(".pdf"):
        return None

    # Each actual PDF has its own record.
    # No grouping by year, date or shift.

    date_label = exam_date or "Date not specified"
    shift_label = shift or "Shift not specified"

    title = (
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
        "title": title,
        "source_url": pdf_url,
        "source_page": source_page,
        "source_authority": "NTA",
        "verification_status": "official_link",
        "source_type": "direct_pdf",
        "source_label": "Official NTA PDF"
    }


# ==================================================
# DISCOVER OFFICIAL QUESTION PAPERS
# ==================================================

def discover_official_papers():

    discovered = {}

    try:
        soup = get_page(SITEMAP_URL)

    except requests.RequestException:
        return []

    # The NTA sitemap contains the actual paper titles
    # and direct PDF destinations.

    for link in soup.find_all("a", href=True):

        title = clean_text(
            link.get_text(" ", strip=True)
        )

        pdf_url = urljoin(
            SITEMAP_URL,
            link["href"]
        )

        if not title:
            continue

        if not is_official_url(pdf_url):
            continue

        if not urlparse(pdf_url).path.lower().endswith(".pdf"):
            continue

        # Use the actual anchor title first.
        # Parent text is supplementary context only.

        context_parts = []

        for parent in link.parents:

            if parent.name in ["tr", "li", "article"]:

                context_parts.append(
                    parent.get_text(" ", strip=True)
                )

                break

        context = " ".join(context_parts)

        record = make_record(
            title,
            context,
            pdf_url,
            SITEMAP_URL
        )

        if record:
            discovered[pdf_url] = record

    return list(discovered.values())


# ==================================================
# YEAR-LEVEL FALLBACKS
# These are NOT individual papers.
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
# Existing API route can continue using this.
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

        # ------------------------------------------
        # INSERT INDIVIDUAL PAPERS
        # ------------------------------------------

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
                    year,
                    session_name,
                    exam_date,
                    shift,
                    paper_type,
                    language,
                    document_type,
                    title,
                    source_url,
                    source_page,
                    source_authority,
                    verification_status,
                    source_type,
                    source_label,
                    created_at,
                    updated_at
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

        # ------------------------------------------
        # INSERT YEAR-LEVEL SOURCE LINKS
        # ------------------------------------------

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
                    year,
                    source_url,
                    source_type,
                    source_label,
                    source_authority,
                    verification_status,
                    created_at,
                    updated_at
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
