
import re
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

CBSE_BASE_URL = "https://www.cbse.gov.in/"


def get_cbse_page(url):
    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 EduSphere Paper Discovery"
        }
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def discover_pdf_links(page_url):
    soup = get_cbse_page(page_url)
    papers = []

    for link in soup.find_all("a", href=True):
        pdf_url = urljoin(page_url, link["href"])
        parsed = urlparse(pdf_url)

        if (
            parsed.path.lower().endswith(".pdf")
            and parsed.netloc.endswith("cbse.gov.in")
        ):
            papers.append({
                "title": link.get_text(" ", strip=True),
                "pdf_url": pdf_url,
                "source_url": page_url
            })

    return papers



def discover_cbse_papers():
    import re

    archive_url = urljoin(
        CBSE_BASE_URL,
        "cbsenew/question-paper.html"
    )

    soup = get_cbse_page(archive_url)
    papers = []

    for link in soup.find_all("a", href=True):
        pdf_url = urljoin(archive_url, link["href"])
        parsed = urlparse(pdf_url)

        if not (
            parsed.path.lower().endswith(".pdf")
            and parsed.netloc.endswith("cbse.gov.in")
        ):
            continue

        match = re.search(
            r"/(\d{4})/(XII|X)/([^/]+)\.pdf$",
            parsed.path,
            re.IGNORECASE
        )

        if not match:
            continue

        year = match.group(1)
        class_code = match.group(2).upper()
        filename = match.group(3)

        class_name = "12" if class_code == "XII" else "10"

        subject_part = re.sub(
            r"^\d+_",
            "",
            filename
        )

        subject = subject_part.replace("_", " ").strip()

        papers.append({
            "exam": "CBSE",
            "class_name": class_name,
            "year": year,
            "subject": subject,
            "subject_code": filename.split("_")[0]
                if "_" in filename else "",
            "session": "Unclassified",
            "title": f"CBSE Class {class_name} {subject} {year}",
            "pdf_url": pdf_url,
            "source_url": archive_url
        })

    return papers

