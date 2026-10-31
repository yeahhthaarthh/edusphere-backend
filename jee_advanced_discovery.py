
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ARCHIVE_URL = "https://jeeadv.ac.in/archive.html"
OFFICIAL_URL = "https://jeeadv.ac.in/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 EduSpherePaperDiscovery/2.0"
}

EXCLUDED = (
    "aat",
    "answer key",
    "answer-key",
    "solution",
    "response sheet",
    "candidate response",
    "admit card",
    "syllabus",
    "brochure",
)


def fetch_soup(url):
    try:
        response = requests.get(
            url, headers=HEADERS, timeout=25
        )
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException:
        return None



def detect_organizing_institute(year, soup=None, page_url=""):
    """
    Detect the organising IIT from official JEE Advanced pages.
    Never guess an institute if an official announcement is absent.
    """

    if soup is None and page_url:
        soup = fetch_soup(page_url)

    if soup is None:
        return ""

    text = soup.get_text(" ", strip=True)

    patterns = [
        r"Organizing Institute\s*[:\-–]\s*"
        r"(Indian Institute of Technology\s+[A-Za-z ]+|IIT\s+[A-Za-z ]+)",

        r"Organising Institute\s*[:\-–]\s*"
        r"(Indian Institute of Technology\s+[A-Za-z ]+|IIT\s+[A-Za-z ]+)",

        r"(?:conducted|organised|organized)\s+by\s+"
        r"(Indian Institute of Technology\s+[A-Za-z ]+|IIT\s+[A-Za-z ]+)",

        r"(?:JEE Advanced|Joint Entrance Examination Advanced)"
        r"\s+" + str(year) + r".{0,100}?"
        r"(?:IIT|Indian Institute of Technology)\s+"
        r"([A-Za-z ]+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if not match:
            continue

        institute = match.group(1).strip()

        institute = re.split(
            r"[|.;,\n]",
            institute,
            maxsplit=1
        )[0].strip()

        institute = re.sub(
            r"^Indian Institute of Technology",
            "IIT",
            institute,
            flags=re.IGNORECASE
        )

        institute = re.sub(r"\s+", " ", institute).strip()

        if institute.upper().startswith("IIT "):
            return institute

    return ""


def excluded(text):
    value = text.lower()
    return any(term in value for term in EXCLUDED)


def detect_stage(text, year):
    value = text.lower()

    if "screening" in value:
        return "Screening"

    if "mains" in value or "main paper" in value:
        return "Mains"

    match = re.search(r"paper\s*[- ]?([12])", value)
    if match:
        return f"Paper {match.group(1)}"

    return "IIT-JEE Paper" if year <= 2006 else "Paper 1"


def detect_language(text):
    value = text.lower()
    return "Hindi" if "hindi" in value else "English"


def make_record(
    year,
    stage,
    language,
    url,
    page,
    authority,
    status,
    exam_date="",
    organizing_institute=""
):
    exam_name = "JEE Advanced" if year >= 2007 else "IIT-JEE"
if not organizing_institute:
    organizing_institute = ORGANIZING_INSTITUTES.get(year, "")
    return {
        "year": year,
        "exam_date": exam_date,
        "paper_type": stage,
        "language": language,
        "document_type": "Question Paper",
        "title": f"{exam_name} {year} {stage} ({language})",
        "source_url": url,
        "download_url": url,
        "storage_path": "",
        "download_mode": "official_external",
        "source_page": page,
        "source_authority": authority,
        "verification_status": status,
        "exam_name": exam_name,
        "stage": stage,
        "organizing_institute": organizing_institute,
        "exam_session": ""
    }


def discover_official_papers():
    soup = fetch_soup(ARCHIVE_URL)
    if soup is None:
        return []

    records = []

    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True)
        href = urljoin(ARCHIVE_URL, anchor["href"])
        context = anchor.parent.get_text(" ", strip=True)
        combined = f"{text} {context} {href}"

        if excluded(combined):
            continue

        if not urlparse(href).path.lower().endswith(".pdf"):
            continue

        year_match = re.search(
            r"\b(2007|2008|2009|20[1-2]\d)\b",
            combined
        )
        if not year_match:
            continue

        year = int(year_match.group(1))
        if year > 2025:
            continue

        stage = detect_stage(combined, year)
        if stage not in ("Paper 1", "Paper 2"):
            continue

        records.append(
            make_record(
                year=year,
                stage=stage,
                language=detect_language(combined),
                url=href,
                page=ARCHIVE_URL,
                authority="JEE Advanced Official",
                status="official_source_link"
            )
        )

    return records


def discover_2026_papers():
    soup = fetch_soup(OFFICIAL_URL)
    if soup is None:
        return []

    records = []
    seen = set()

    institute = detect_organizing_institute(
        2026, soup=soup, page_url=OFFICIAL_URL
    )

    for anchor in soup.find_all("a", href=True):
        href = urljoin(OFFICIAL_URL, anchor["href"])
        filename = urlparse(href).path.rsplit("/", 1)[-1].lower()

        match = re.fullmatch(
            r"p([12])_(english|hindi)\.pdf",
            filename
        )

        if not match or href in seen:
            continue

        seen.add(href)

        records.append(
            make_record(
                year=2026,
                stage=f"Paper {match.group(1)}",
                language=match.group(2).capitalize(),
                url=href,
                page=OFFICIAL_URL,
                authority="JEE Advanced Official",
                status="official_source_link",
                exam_date="2026-05-17",
                organizing_institute="IIT Roorkee"
            )
        )

    return records


def discover_jee_advanced_papers():
    records = []
    records.extend(discover_official_papers())
    records.extend(discover_2026_papers())

    unique = {}
    for record in records:
        unique[record["source_url"]] = record

    return list(unique.values())


def sync_jee_advanced_papers():
    records = discover_jee_advanced_papers()

    if not records:
        return {
            "success": False,
            "message": "No official paper links found.",
            "discovered": 0,
            "inserted": 0,
            "updated": 0
        }

    from app import connect

    inserted = 0
    updated = 0

    with connect() as db:
        with db.cursor() as cur:
            for record in records:
                now = int(time.time())

                cur.execute(
                    """
                    INSERT INTO jee_advanced_papers (
                        year, exam_date, paper_type, language,
                        document_type, title, source_url,
                        source_page, source_authority,
                        verification_status, created_at,
                        updated_at, exam_name, stage,
                        organizing_institute, exam_session,
                        download_url, storage_path, download_mode
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (source_url) DO UPDATE SET
                        download_url = EXCLUDED.download_url,
                        download_mode = EXCLUDED.download_mode,
                        updated_at = EXCLUDED.updated_at
                    RETURNING (xmax = 0) AS was_inserted
                    """,
                    (
                        record["year"],
                        record["exam_date"],
                        record["paper_type"],
                        record["language"],
                        record["document_type"],
                        record["title"],
                        record["source_url"],
                        record["source_page"],
                        record["source_authority"],
                        record["verification_status"],
                        now,
                        now,
                        record["exam_name"],
                        record["stage"],
                        record["organizing_institute"],
                        record["exam_session"],
                        record["download_url"],
                        record["storage_path"],
                        record["download_mode"]
                    )
                )

                result = cur.fetchone()
                if result and result["was_inserted"]:
                    inserted += 1
                else:
                    updated += 1

    return {
        "success": True,
        "message": "JEE Advanced PDF links synced.",
        "discovered": len(records),
        "inserted": inserted,
        "updated": updated
    }
