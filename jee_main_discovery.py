
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


BASE_URL = "https://jeemain.nta.nic.in/"
SITEMAP_URL = urljoin(BASE_URL, "sitemap/")
DOCUMENTS_URL = urljoin(BASE_URL, "documents/")

HEADERS = {
    "User-Agent": "Mozilla/5.0 EduSphere JEE Main Discovery"
}

ALLOWED_HOSTS = {
    "cdnbbsr.s3waas.gov.in",
    "nta.ac.in",
    "www.nta.ac.in"
}


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


def is_official_pdf(url):
    parsed = urlparse(url)

    return (
        parsed.scheme == "https"
        and parsed.netloc.lower() in ALLOWED_HOSTS
        and parsed.path.lower().endswith(".pdf")
    )


def identify_paper_type(title):
    text = title.lower()

    if "b.planning" in text or "b planning" in text:
        return "Paper 2B"

    if "b.arch" in text or "b arch" in text:
        return "Paper 2A"

    if "b tech" in text or "b.tech" in text:
        return "Paper 1"

    return ""


def extract_date(title):
    match = re.search(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(Jan|January|Feb|February|Mar|March|"
        r"Apr|April|May|Jun|June|Jul|July|"
        r"Aug|August|Sep|September|Oct|October|"
        r"Nov|November|Dec|December)\s+"
        r"(20\d{2})",
        title,
        re.IGNORECASE
    )

    if not match:
        return "", ""

    day = int(match.group(1))
    month = match.group(2).lower()
    year = match.group(3)

    month_map = {
        "jan": "01", "january": "01",
        "feb": "02", "february": "02",
        "mar": "03", "march": "03",
        "apr": "04", "april": "04",
        "may": "05",
        "jun": "06", "june": "06",
        "jul": "07", "july": "07",
        "aug": "08", "august": "08",
        "sep": "09", "september": "09",
        "oct": "10", "october": "10",
        "nov": "11", "november": "11",
        "dec": "12", "december": "12"
    }

    return (
        f"{year}-{month_map[month]}-{day:02d}",
        year
    )


def extract_session(title):
    text = title.lower()

    if "session-ii" in text or "session 2" in text:
        return "Session 2"

    if "session-i" in text or "session 1" in text:
        return "Session 1"

    exam_date, year = extract_date(title)

    if exam_date:
        month = int(exam_date.split("-")[1])

        if month <= 2:
            return "Session 1"

        if month >= 3:
            return "Session 2"

    return "Not specified"


def extract_shift(title):
    match = re.search(
        r"shift\s*[-:]?\s*(1|2)",
        title,
        re.IGNORECASE
    )

    return f"Shift {match.group(1)}" if match else ""


def extract_language(title):
    text = title.lower()

    languages = [
        "Hindi", "English", "Assamese",
        "Bengali", "Gujarati", "Kannada",
        "Malayalam", "Marathi", "Odia",
        "Punjabi", "Tamil", "Telugu", "Urdu"
    ]

    found = [
        language
        for language in languages
        if language.lower() in text
    ]

    return ", ".join(found) if found else "Not specified"


def make_record(title, pdf_url, source_page):
    paper_type = identify_paper_type(title)

    if not paper_type:
        return None

    exam_date, year = extract_date(title)

    if not year:
        year_match = re.search(r"20\d{2}", title)

        if year_match:
            year = year_match.group(0)

    if not year:
        return None

    lower_title = title.lower()

    if "answer key" in lower_title or "answer keys" in lower_title:
        document_type = "Answer Key"
    elif "question paper" in lower_title or "b tech" in lower_title or "b.arch" in lower_title or "b planning" in lower_title:
        document_type = "Question Paper"
    else:
        return None

    session = extract_session(title)

    shift = extract_shift(title)

    clean_title = re.sub(
        r"\s+",
        " ",
        title
    ).strip()

    return {
        "year": int(year),
        "session_name": session,
        "exam_date": exam_date,
        "shift": shift,
        "paper_type": paper_type,
        "language": extract_language(title),
        "document_type": document_type,
        "title": clean_title,
        "source_url": pdf_url,
        "source_page": source_page,
        "source_authority": "NTA",
        "verification_status": "official_link"
    }


def discover_question_papers():
    soup = get_page(SITEMAP_URL)
    discovered = {}

    for link in soup.find_all("a", href=True):
        title = link.get_text(
            " ",
            strip=True
        )

        pdf_url = urljoin(
            SITEMAP_URL,
            link["href"]
        )

        if not is_official_pdf(pdf_url):
            continue

        record = make_record(
            title,
            pdf_url,
            SITEMAP_URL
        )

        if record:
            discovered[pdf_url] = record

    return discovered


def discover_answer_keys():
    discovered = {}
    pages_to_scan = [DOCUMENTS_URL]
    scanned = set()

    while pages_to_scan and len(scanned) < 10:
        page_url = pages_to_scan.pop(0)

        if page_url in scanned:
            continue

        scanned.add(page_url)

        try:
            soup = get_page(page_url)
        except requests.RequestException:
            continue

        for link in soup.find_all("a", href=True):
            title = link.get_text(
                " ",
                strip=True
            )

            target_url = urljoin(
                page_url,
                link["href"]
            )

            path = urlparse(target_url).path.lower()

            if "/documents/page/" in path:
                if target_url not in scanned:
                    pages_to_scan.append(target_url)

            if not is_official_pdf(target_url):
                continue

            if "answer key" not in title.lower() and "answer keys" not in title.lower():
                continue

            record = make_record(
                title,
                target_url,
                page_url
            )

            if record:
                discovered[target_url] = record

    return discovered


def discover_jee_main_papers():
    question_papers = discover_question_papers()
    answer_keys = discover_answer_keys()

    combined = {
        **question_papers,
        **answer_keys
    }

    return list(combined.values())


def sync_jee_main_papers():
    from app import connect

    papers = discover_jee_main_papers()

    added = 0
    skipped = 0

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

            now = int(time.time())

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
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
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
                    now,
                    now
                )
            )

            added += 1

    return {
        "success": True,
        "discovered": len(papers),
        "added": added,
        "skipped": skipped
    }
