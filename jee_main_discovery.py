
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

BASE_URL = "https://jeemain.nta.nic.in/"
SITEMAP_URL = urljoin(BASE_URL, "sitemap/")

HEADERS = {
    "User-Agent": "Mozilla/5.0 EduSphere JEE Main Discovery"
}

ALLOWED_HOSTS = {
    "jeemain.nta.nic.in",
    "nta.ac.in",
    "www.nta.ac.in",
    "cdnbbsr.s3waas.gov.in",
}

FIRST_YEAR = 2014
LAST_YEAR = 2026


# --------------------------------------------------
# GENERAL HELPERS
# --------------------------------------------------

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

    return BeautifulSoup(response.text, "html.parser")


def extract_year(text):
    match = re.search(
        r"\b(201[4-9]|202[0-6])\b",
        text
    )

    return int(match.group(1)) if match else None


# --------------------------------------------------
# PAPER CLASSIFICATION
# --------------------------------------------------

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


def identify_document_type(text):
    text = text.lower()

    if "answer key" in text or "answer-key" in text:
        return "Answer Key"

    if (
        "question paper" in text
        or "question-paper" in text
        or "b.tech" in text
        or "b.tech." in text
        or "b.arch" in text
        or "b.planning" in text
    ):
        return "Question Paper"

    return None


# --------------------------------------------------
# SESSION, DATE AND SHIFT
# --------------------------------------------------

def extract_session(text):
    text = text.lower()

    if re.search(r"session[\s_-]*1\b", text):
        return "Session 1"

    if re.search(r"session[\s_-]*2\b", text):
        return "Session 2"

    if "january" in text or "jan " in text:
        return "Session 1"

    if "april" in text or "march" in text:
        return "Session 2"

    return "Not specified"


def extract_shift(text):
    match = re.search(
        r"\bshift\s*[-:]?\s*([12])\b",
        text,
        re.I
    )

    if match:
        return f"Shift {match.group(1)}"

    return ""


def extract_exam_date(text):
    from datetime import datetime

    months = (
        "January|February|March|April|May|June|July|"
        "August|September|October|November|December"
    )

    patterns = [
        rf"\b(\d{{1,2}})\s+({months})\s+(20\d{{2}})\b",
        rf"\b({months})\s+(\d{{1,2}}),?\s+(20\d{{2}})\b"
    ]

    for index, pattern in enumerate(patterns):
        match = re.search(pattern, text, re.I)

        if not match:
            continue

        try:
            if index == 0:
                date_text = match.group(0)
                parsed = datetime.strptime(
                    date_text,
                    "%d %B %Y"
                )
            else:
                month, day, year = match.groups()
                parsed = datetime.strptime(
                    f"{day} {month} {year}",
                    "%d %B %Y"
                )

            return parsed.strftime("%Y-%m-%d")

        except ValueError:
            continue

    return ""


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


# --------------------------------------------------
# BUILD INDIVIDUAL PAPER RECORDS
# --------------------------------------------------

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

    document_type = identify_document_type(
        combined_text
    )

    if not document_type:
        return None

    exam_date = extract_exam_date(combined_text)
    shift = extract_shift(combined_text)
    session = extract_session(combined_text)
    language = extract_language(combined_text)

    # Avoid treating a generic portal link as a paper.
    if not pdf_url.lower().split("?")[0].endswith(".pdf"):
        return None

    return {
        "year": year,
        "session_name": session,
        "exam_date": exam_date,
        "shift": shift,
        "paper_type": paper_type,
        "language": language,
        "document_type": document_type,
        "title": (
            f"JEE Main {year} | {session} | "
            f"{exam_date or 'Date not specified'} | "
            f"{shift or 'Shift not specified'} | "
            f"{paper_type} | {document_type}"
        ),
        "source_url": pdf_url,
        "source_page": source_page,
        "source_authority": "NTA",
        "verification_status": "official_link",
        "source_type": "direct_pdf",
        "source_label": "Official NTA PDF"
    }


# --------------------------------------------------
# DISCOVER OFFICIAL PAPERS
# --------------------------------------------------

def discover_official_papers():

    discovered = {}

    pages_to_scan = [
        BASE_URL,
        SITEMAP_URL
    ]

    for page_url in pages_to_scan:

        try:
            soup = get_page(page_url)

        except requests.RequestException:
            continue

        for link in soup.find_all("a", href=True):

            title = clean_text(
                link.get_text(" ", strip=True)
            )

            pdf_url = urljoin(
                page_url,
                link["href"]
            )

            if not title:
                continue

            if not is_official_url(pdf_url):
                continue

            if not urlparse(pdf_url).path.lower().endswith(".pdf"):
                continue

            # Include nearby table/row/parent text.
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
                page_url
            )

            if not record:
                continue

            # Each different PDF URL remains a separate record.
            discovered[pdf_url] = record

    return list(discovered.values())


# --------------------------------------------------
# YEAR-LEVEL FALLBACK LINKS
# These are NOT paper records.
# --------------------------------------------------

def discover_year_fallbacks(papers):

    years_with_direct_papers = {
        paper["year"] for paper in papers
    }

    fallbacks = []

    for year in range(FIRST_YEAR, LAST_YEAR + 1):

        if year in years_with_direct_papers:
            continue

        fallbacks.append({
            "year": year,
            "source_url": BASE_URL,
            "source_type": "official_page",
            "source_label": (
                f"Official NTA JEE Main portal - "
                f"check {year} archive"
            ),
            "source_authority": "NTA",
            "verification_status": "portal_only"
        })

    return fallbacks


# --------------------------------------------------
# DISCOVERY FUNCTION
# --------------------------------------------------

def discover_jee_main_papers():

    papers = discover_official_papers()

    # Store fallback information separately.
    # Never add fake shifts or fake papers.
    fallbacks = discover_year_fallbacks(papers)

    return papers


# --------------------------------------------------
# DATABASE SYNC
# --------------------------------------------------

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
        # INSERT REAL PAPER RECORDS
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
        # INSERT YEAR-LEVEL FALLBACK LINKS
        # ------------------------------------------

        for fallback in fallbacks:

            existing = db.execute(
                """
                SELECT id
                FROM jee_main_year_sources
                WHERE year = %s AND source_url = %s
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
