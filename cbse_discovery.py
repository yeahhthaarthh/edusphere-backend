
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


CBSE_BASE_URL = "https://www.cbse.gov.in/"
ARCHIVE_URL = urljoin(
    CBSE_BASE_URL,
    "cbsenew/question-paper.html"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 EduSphere Paper Discovery"
}

MIN_YEAR = 2010
MAX_YEAR = 2026


def get_cbse_page(url):
    response = requests.get(
        url,
        timeout=30,
        headers=HEADERS
    )
    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser"
    )


def is_official_cbse_url(url):
    host = urlparse(url).netloc.lower()

    return (
        host == "cbse.gov.in"
        or host.endswith(".cbse.gov.in")
    )


def get_year_and_class(pdf_url):
    path = urlparse(pdf_url).path

    year_match = re.search(
        r"/(20\d{2})/",
        path
    )

    class_match = re.search(
        r"/(XII|X|CLASS[-_ ]?12|CLASS[-_ ]?10)/",
        path,
        re.IGNORECASE
    )

    if not year_match or not class_match:
        return None, None

    year = int(year_match.group(1))
    class_code = class_match.group(1).upper()

    if year < MIN_YEAR or year > MAX_YEAR:
        return None, None

    if class_code in ("XII", "CLASS12", "CLASS-12", "CLASS_12"):
        class_name = "12"
    else:
        class_name = "10"

    return str(year), class_name


def get_subject_details(link):
    row = link.find_parent("tr")

    if row:
        cells = row.find_all(["td", "th"])

        if cells:
            subject = cells[0].get_text(
                " ",
                strip=True
            )

            if subject and subject.lower() not in (
                "subject name",
                "subject"
            ):
                return subject, ""

    filename = urlparse(
        link["href"]
    ).path.rsplit("/", 1)[-1]

    filename = re.sub(
        r"\.pdf$",
        "",
        filename,
        flags=re.IGNORECASE
    )

    code_match = re.match(
        r"^(\d+)[_-](.+)$",
        filename
    )

    if code_match:
        code = code_match.group(1)
        subject = code_match.group(2)
    else:
        code = ""
        subject = filename

    subject = subject.replace("_", " ")
    subject = subject.replace("-", " ").strip()

    return subject, code


def get_exam_type(link):
    for element in link.previous_elements:
        if not getattr(element, "name", None):
            continue

        if element.name not in (
            "h1", "h2", "h3", "h4",
            "button", "strong"
        ):
            continue

        heading = element.get_text(
            " ",
            strip=True
        ).lower()

        if "compartment" in heading:
            return "Compartment"

        if "second board" in heading:
            return "Second Board"

        if "sample paper" in heading:
            return "Sample Paper"

        if "question paper" in heading or "examination" in heading:
            return "Regular"

    path = urlparse(
        link["href"]
    ).path.lower()

    if "compartment" in path:
        return "Compartment"

    return "Unclassified"


def discover_archive_pages():
    pages = {ARCHIVE_URL}

    soup = get_cbse_page(ARCHIVE_URL)

    keywords = (
        "question paper",
        "previous year",
        "archive",
        "old paper"
    )

    for link in soup.find_all("a", href=True):
        text = link.get_text(
            " ",
            strip=True
        ).lower()

        if not any(word in text for word in keywords):
            continue

        page_url = urljoin(
            ARCHIVE_URL,
            link["href"]
        )

        parsed = urlparse(page_url)

        if (
            is_official_cbse_url(page_url)
            and not parsed.path.lower().endswith(".pdf")
        ):
            pages.add(page_url)

    return sorted(pages)


def discover_cbse_papers():
    pages = discover_archive_pages()
    discovered = {}

    for page_url in pages:
        try:
            soup = get_cbse_page(page_url)

        except requests.RequestException:
            continue

        for link in soup.find_all("a", href=True):
            pdf_url = urljoin(
                page_url,
                link["href"]
            )

            parsed = urlparse(pdf_url)

            if not (
                parsed.path.lower().endswith(".pdf")
                and is_official_cbse_url(pdf_url)
            ):
                continue

            year, class_name = get_year_and_class(
                pdf_url
            )

            if not year or not class_name:
                continue

            subject, subject_code = get_subject_details(
                link
            )

            if not subject:
                continue

            session = get_exam_type(link)

            title = (
                f"CBSE Class {class_name} "
                f"{subject} {year} "
                f"{session}"
            )

            discovered[pdf_url] = {
                "exam": "CBSE",
                "class_name": class_name,
                "year": year,
                "subject": subject,
                "subject_code": subject_code,
                "session": session,
                "title": title,
                "pdf_url": pdf_url,
                "source_url": page_url
            }

    return list(discovered.values())


def sync_cbse_papers():
    from app import connect

    papers = discover_cbse_papers()

    added = 0
    skipped = 0

    with connect() as db:
        for paper in papers:
            existing = db.execute(
                """
                SELECT id
                FROM papers
                WHERE source_url = %s
                """,
                (paper["pdf_url"],)
            ).fetchone()

            if existing:
                skipped += 1
                continue

            now = int(time.time())

            db.execute(
                """
                INSERT INTO papers (
                    exam,
                    year,
                    subject,
                    session,
                    title,
                    description,
                    source_url,
                    file_name,
                    stored_name,
                    file_size,
                    downloads,
                    created_at,
                    updated_at,
                    class_name,
                    subject_code
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                """,
                (
                    paper["exam"],
                    paper["year"],
                    paper["subject"],
                    paper["session"],
                    paper["title"],
                    "Official CBSE question paper",
                    paper["pdf_url"],
                    "",
                    "EXTERNAL_URL",
                    0,
                    0,
                    now,
                    now,
                    paper["class_name"],
                    paper["subject_code"]
                )
            )

            added += 1

    return {
        "success": True,
        "discovered": len(papers),
        "added": added,
        "skipped": skipped
    }
