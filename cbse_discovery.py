
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


ARCHIVE_URL = (
    "https://www.cbse.gov.in/cbsenew/question-paper.html"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 EduSphere Paper Discovery"
}


def get_page(url):
    response = requests.get(
        url,
        timeout=40,
        headers=HEADERS
    )
    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser"
    )


def official_url(url):
    host = urlparse(url).netloc.lower()

    return (
        host == "cbse.gov.in"
        or host.endswith(".cbse.gov.in")
    )


def get_exam_details(heading):
    text = heading.lower()

    year_match = re.search(r"20\d{2}", text)

    if not year_match:
        return None

    if "class xii" in text:
        class_name = "12"
    elif "class x" in text:
        class_name = "10"
    else:
        return None

    if "compartment" in text:
        session = "Compartment"
    elif "second board" in text:
        session = "Second Board"
    else:
        session = "Regular"

    return {
        "year": year_match.group(),
        "class_name": class_name,
        "session": session
    }


def extract_subject_code(url):
    filename = urlparse(url).path.rsplit("/", 1)[-1]

    match = re.match(r"(\d+)[_-]", filename)

    return match.group(1) if match else ""


def discover_cbse_papers():
    soup = get_page(ARCHIVE_URL)
    discovered = {}

    for table in soup.find_all("table"):
        heading = table.find_previous(
            ["h1", "h2", "h3", "h4"]
        )

        if not heading:
            continue

        details = get_exam_details(
            heading.get_text(" ", strip=True)
        )

        if not details:
            continue

        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])

            if len(cells) < 2:
                continue

            subject = cells[0].get_text(
                " ",
                strip=True
            )

            if not subject or subject.lower() in (
                "subject name",
                "subject"
            ):
                continue

            for link in cells[1].find_all(
                "a",
                href=True
            ):
                file_url = urljoin(
                    ARCHIVE_URL,
                    link["href"]
                )

                path = urlparse(file_url).path.lower()

                if not (
                    official_url(file_url)
                    and path.endswith((".pdf", ".zip"))
                ):
                    continue

                subject_code = extract_subject_code(
                    file_url
                )

                title = (
                    f"CBSE Class {details['class_name']} "
                    f"{subject} {details['year']} "
                    f"{details['session']}"
                )

                discovered[file_url] = {
                    "exam": "CBSE",
                    "class_name": details["class_name"],
                    "year": details["year"],
                    "subject": subject,
                    "subject_code": subject_code,
                    "session": details["session"],
                    "title": title,
                    "pdf_url": file_url,
                    "source_url": file_url
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
                    exam, year, subject, session,
                    title, description, source_url,
                    file_name, stored_name, file_size,
                    downloads, created_at, updated_at,
                    class_name, subject_code
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
