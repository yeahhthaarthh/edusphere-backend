import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

CBSE_BASE_URL = "https://www.cbse.gov.in/"

def get_cbse_page(url):
    response = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "EduSphere Paper Discovery"}
    )
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")
  def discover_pdf_links(page_url):
    soup = get_cbse_page(page_url)
    papers = []

    for link in soup.find_all("a", href=True):
        pdf_url = urljoin(page_url, link["href"])

        if urlparse(pdf_url).path.lower().endswith(".pdf"):
            papers.append({
                "title": link.get_text(" ", strip=True),
                "pdf_url": pdf_url,
                "source_url": page_url
            })

    return papers
    
import re

def discover_cbse_papers():
    archive_url = urljoin(
        CBSE_BASE_URL,
        "cbsenew/question-paper.html"
    )

    soup = get_cbse_page(archive_url)
    papers = []

    for heading in soup.find_all(["h2", "h3"]):
        heading_text = heading.get_text(" ", strip=True)

        match = re.search(
            r"Class\s+(XII|X)\s+.*?(\d{4})",
            heading_text,
            re.IGNORECASE
        )

        if not match:
            continue

        class_name = "12" if match.group(1).upper() == "XII" else "10"
        year = match.group(2)

        exam_type = (
            "Compartment"
            if "compartment" in heading_text.lower()
            else "Regular"
        )

        table = heading.find_next("table")

        if not table:
            continue

        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])

            if len(cells) < 2:
                continue

            subject = cells[0].get_text(" ", strip=True)
            link = cells[1].find("a", href=True)

            if not subject or not link:
                continue

            pdf_url = urljoin(archive_url, link["href"])

            if not urlparse(pdf_url).netloc.endswith("cbse.gov.in"):
                continue

            papers.append({
                "exam": "CBSE",
                "class_name": class_name,
                "year": year,
                "subject": subject,
                "session": exam_type,
                "title": f"CBSE Class {class_name} {subject} {year}",
                "source_url": archive_url,
                "pdf_url": pdf_url
            })

    return papers
