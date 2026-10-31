from urllib.parse import urljoin, urlparse
import re
import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

ARCHIVE_URL = "https://jeeadv.ac.in/archive.html"
VEDCLASS_URL = "https://www.vedclass.com/exam/iit-previous-year-question"
EXAMGOAL_URL = (
    "https://pdf.questions.examgoal.com/past-years/"
    "year-wise/jee/jee-advanced"
)

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
            url,
            headers=HEADERS,
            timeout=25
        )
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException:
        return None
def detect_organizing_institute(year, soup=None, page_url=""):
    """
    Detect the organising IIT from an official JEE Advanced page.
    Return an empty string if it cannot be verified.
    """

    if soup is None and page_url:
        soup = fetch_soup(page_url)

    if soup is None:
        return ""

    text = soup.get_text(" ", strip=True)

    patterns = [
        r"Organizing Institute\s*[:\-–]\s*"
        r"(Indian Institute of Technology\s+[\w\s]+)",

        r"Organising Institute\s*[:\-–]\s*"
        r"(Indian Institute of Technology\s+[\w\s]+)",

        r"Organizing Institute\s*[:\-–]\s*"
        r"(IIT\s*[\w\s]+)",

        r"Organising Institute\s*[:\-–]\s*"
        r"(IIT\s*[\w\s]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            institute = match.group(1).strip()

            institute = re.split(
                r"(?=Participating Institutes|Important Announcements|Contact Details)",
                institute,
                maxsplit=1,
                flags=re.IGNORECASE
            )[0].strip()

            if institute:
                institute = re.sub(
                    r"^Indian Institute of Technology",
                    "IIT",
                    institute,
                    flags=re.IGNORECASE
                )

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

    if year <= 2006:
        return "IIT-JEE Paper"

    return "Paper 1"


def detect_language(text):
    value = text.lower()

    if "hindi" in value:
        return "Hindi"

    if "gujarati" in value:
        return "Gujarati"

    return "English"


def make_record(
    year,
    stage,
    language,
    url,
    page,
    authority,
    status,
    exam_date,
    organising_institute=""
):
    return {
        "year": year,
        "exam_date": exam_date,
        "paper_type": stage,
        "language": language,
        "document_type": "Question Paper",
       "title": f"{'JEE Advanced' if year >= 2007 else 'IIT-JEE'} {year} {stage} ({language})",
        "source_url": url,
        "source_page": page,
        "source_authority": authority,
        "verification_status": status,
        "exam_name": (
            "JEE Advanced" if year >= 2007 else "IIT-JEE"
        ),
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

        year_match = re.search(r"\b(2007|2008|2009|20[1-2]\d)\b", combined)

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
                year,
                stage,
                detect_language(combined),
                href,
                ARCHIVE_URL,
                "JEE Advanced Official",
                "official_source_link"
            )
        )

    return records


def discover_2026_papers():
    url = "https://jeeadv.ac.in/"
    soup = fetch_soup(url)

    if soup is None:
        return []

    records = []
    seen = set()

    for anchor in soup.find_all("a", href=True):
        href = urljoin(url, anchor["href"])
        path = urlparse(href).path.lower()
        filename = path.rsplit("/", 1)[-1]

        # Identify paper number from the actual PDF filename.
        paper_match = re.fullmatch(
            r"p([12])_(english|hindi)\.pdf",
            filename
        )

        if not paper_match:
            continue

        if href in seen:
            continue

        seen.add(href)

        paper_number = paper_match.group(1)
        language = paper_match.group(2).capitalize()

        paper_type = f"Paper {paper_number}"

        records.append(
      make_record(
    year=2026,
    stage=paper_type,
    language=language,
    url=href,
    page=url,
    authority="JEE Advanced Official",
    status="official_source_link",
    exam_date="2026-05-17",
    organizing_institute=detect_organizing_institute(
        year=2026,
        soup=soup,
        page_url=url
    )
)

    return records



def discover_historical_catalogue():
    """
    Collects historical year/stage source-page references.

    These are NOT treated as verified question-paper PDFs.
    They are retained separately for manual verification.
    """

    soup = fetch_soup(VEDCLASS_URL)

    if soup is None:
        return []

    records = []

    for anchor in soup.find_all("a", href=True):
        text = anchor.get_text(" ", strip=True)
        combined = f"{text} {anchor.parent.get_text(' ', strip=True)}"

        year_match = re.search(
            r"\b(19[6-9]\d|200[0-6])\b",
            combined
        )

        if not year_match:
            continue

        year = int(year_match.group(1))

        if year >= 2007:
            continue

        stage = detect_stage(combined, year)
        href = urljoin(VEDCLASS_URL, anchor["href"])

        records.append(
            make_record(
                year,
                stage,
                detect_language(combined),
                href,
                VEDCLASS_URL,
                "Vedclass (third-party index)",
                "third_party_page_unverified"
            )
        )

    return records


def discover_jee_advanced_papers():
    records = []

    records.extend(discover_official_papers())
    records.extend(discover_2026_papers())

    # Historical catalogue references are intentionally
    # not inserted as downloadable question-paper records.
    # They need direct PDF and content verification first.

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
            "inserted": 0
        }

    # Import connect only when sync runs to avoid circular imports.
    from app import connect

    inserted = 0

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
                        organizing_institute, exam_session
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (source_url) DO NOTHING
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
                        record["exam_session"]
                    )
                )

                if cur.rowcount:
                    inserted += 1

    return {
        "success": True,
        "message": "Official JEE Advanced paper sync completed.",
        "discovered": len(records),
        "inserted": inserted
    }
