
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

        title = link.get_text(" ", strip=True)

        papers.append({
            "exam": "CBSE",
            "title": title,
            "pdf_url": pdf_url,
            "source_url": archive_url
        })

    return papers
