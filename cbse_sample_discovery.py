
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


BASE_URL = "https://cbseacademic.nic.in/"
ARCHIVE_URL = urljoin(BASE_URL, "sqp_archive.html")

HEADERS = {
    "User-Agent": "Mozilla/5.0 EduSphere Sample Paper Discovery"
}

MIN_YEAR = 2014
MAX_YEAR = 2027


def get_page(url):
    response = requests.get(
        url,
        timeout=30,
        headers=HEADERS
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def is_official_url(url):
    host = urlparse(url).netloc.lower()

    return (
        host == "cbseacademic.nic.in"
        or host.endswith(".cbseacademic.nic.in")
    )


def get_archive_pages():
    soup = get_page(ARCHIVE_URL)
    pages = {}

    for link in soup.find_all("a", href=True):
        href = link["href"]
        page_url = urljoin(ARCHIVE_URL, href)

        if not is_official_url(page_url):
            continue

        path = urlparse(page_url).path.upper()

        class_match = re.search(
            r"CLASS(XII|X)(?:_|\.|-)",
            path
        )

        session_match = re.search(
            r"(20\d{2})[-_](\d{2,4})",
            path
        )

        if not class_match or not session_match:
            continue

        class_code = class_match.group(1)
        class_name = "12" if class_code == "XII" else "10"

        start_year = int(session_match.group(1))
        end_part = session_match.group(2)

        if len(end_part) == 2:
            academic_session = (
                f"{start_year}-{end_part}"
            )
        else:
            academic_session = (
                f"{start_year}-{end_part[-2:]}"
            )

        pages[page_url] = {
            "class_name": class_name,
            "academic_session": academic_session
        }

    return pages


def identify_document_type(link):
    text = link.get_text(
        " ",
        strip=True
    ).lower()

    url = link.get("href", "").lower()

    if (
        re.search(r"\bms\b", text)
        or "marking" in text
        or "-ms." in url
        or "_ms." in url
    ):
        return "Marking Scheme"

    if (
        "sqp" in text
        or "sample question" in text
        or url.lower().endswith(".pdf")
    ):
        return "Sample Question Paper"

    return None


def discover_sample_papers():
    archive_pages = get_archive_pages()
    discovered = {}

    for page_url, metadata in archive_pages.items():
        try:
            soup = get_page(page_url)
        except requests.RequestException:
            continue

        for row in soup.find_all("tr"):
            cells = row.find_all(["td", "th"])

            if len(cells) < 2:
                continue

            subject = cells[0].get_text(
                " ",
                strip=True
            )

            if not subject:
                continue

            for link in row.find_all("a", href=True):
                pdf_url = urljoin(
                    page_url,
                    link["href"]
                )

                if not (
                    is_official_url(pdf_url)
                    and urlparse(pdf_url).path.lower().endswith(".pdf")
                ):
                    continue

                document_type = identify_document_type(link)

                if not document_type:
                    continue

                title = (
                    f"CBSE Class {metadata['class_name']} "
                    f"{subject} "
                    f"{metadata['academic_session']} "
                    f"{document_type}"
                )

                discovered[pdf_url] = {
                    "exam": "CBSE",
                    "class_name": metadata["class_name"],
                    "academic_session": metadata["academic_session"],
                    "subject": subject,
                    "document_type": document_type,
                    "title": title,
                    "source_url": pdf_url,
                    "source_page": page_url
                }

    return list(discovered.values())


def sync_sample_papers():
    from app import connect

    papers = discover_sample_papers()

    added = 0
    skipped = 0

    with connect() as db:
        for paper in papers:
            existing = db.execute(
                """
                SELECT id
                FROM sample_papers
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
                INSERT INTO sample_papers (
                    exam,
                    class_name,
                    academic_session,
                    subject,
                    document_type,
                    title,
                    source_url,
                    source_page,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                """,
                (
                    paper["exam"],
                    paper["class_name"],
                    paper["academic_session"],
                    paper["subject"],
                    paper["document_type"],
                    paper["title"],
                    paper["source_url"],
                    paper["source_page"],
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
