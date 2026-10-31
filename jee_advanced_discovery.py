import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# =========================================================
# CONFIGURATION
# =========================================================

ARCHIVE_URL = "https://jeeadv.ac.in/archive.html"
OFFICIAL_URL = "https://jeeadv.ac.in/"
OFFICIAL_HOST = "jeeadv.ac.in"

HEADERS = {
    "User-Agent": "Mozilla/5.0 EduSpherePaperDiscovery/4.0"
}

REQUEST_TIMEOUT = 25

EXCLUDED_TERMS = (
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

ORGANIZING_INSTITUTES = {
    2007: "IIT Bombay",
    2008: "IIT Roorkee",
    2009: "IIT Guwahati",
    2010: "IIT Madras",
    2011: "IIT Kanpur",
    2012: "IIT Delhi",
    2013: "IIT Delhi",
    2014: "IIT Kharagpur",
    2015: "IIT Bombay",
    2016: "IIT Guwahati",
    2017: "IIT Madras",
    2018: "IIT Kanpur",
    2019: "IIT Roorkee",
    2020: "IIT Delhi",
    2021: "IIT Kharagpur",
    2022: "IIT Bombay",
    2023: "IIT Guwahati",
    2024: "IIT Madras",
    2025: "IIT Kanpur",
    2026: "IIT Roorkee",
}

EXAM_DATES = {
    2026: "2026-05-17",
}


# =========================================================
# OFFICIAL URL VALIDATION
# =========================================================

def is_official_url(url):
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme == "https"
            and parsed.hostname == OFFICIAL_HOST
        )

    except (ValueError, TypeError):
        return False


# =========================================================
# WEBPAGE FETCHING
# =========================================================

def fetch_soup(url):

    if not is_official_url(url):
        print(f"Rejected non-official URL: {url}")
        return None

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT
        )

        response.raise_for_status()

        if not is_official_url(response.url):
            print("Rejected redirected non-official URL.")
            return None

        return BeautifulSoup(
            response.text,
            "html.parser"
        )

    except requests.RequestException as error:
        print(f"EduSphere discovery fetch error: {error}")
        return None


# =========================================================
# ORGANISING INSTITUTE DETECTION
# =========================================================

def normalize_institute(name):

    if not name:
        return ""

    name = re.sub(
        r"^Indian Institute of Technology",
        "IIT",
        name.strip(),
        flags=re.IGNORECASE
    )

    name = re.sub(r"\s+", " ", name)
    name = name.strip(" .,:;|-")

    return name


def detect_organizing_institute(
    year,
    soup=None,
    page_url=""
):

    if year in ORGANIZING_INSTITUTES:
        return ORGANIZING_INSTITUTES[year]

    if soup is None and page_url:
        soup = fetch_soup(page_url)

    if soup is None:
        return ""

    text = soup.get_text(" ", strip=True)

    patterns = [
        r"(?:Organizing|Organising)\s+Institute"
        r"\s*[:\-–]\s*"
        r"(Indian Institute of Technology\s+[A-Za-z ]+|IIT\s+[A-Za-z ]+)",

        r"(?:conducted|organized|organised)\s+by\s+"
        r"(Indian Institute of Technology\s+[A-Za-z ]+|IIT\s+[A-Za-z ]+)",

        r"JEE\s+Advanced\s+" + str(year)
        + r".{0,150}?"
        + r"(Indian Institute of Technology\s+[A-Za-z ]+|IIT\s+[A-Za-z ]+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if not match:
            continue

        institute = normalize_institute(match.group(1))

        institute = re.split(
            r"[,.;|()]",
            institute,
            maxsplit=1
        )[0].strip()

        if re.fullmatch(
            r"IIT\s+[A-Za-z ]+",
            institute,
            flags=re.IGNORECASE
        ):
            return institute

    return ""


# =========================================================
# PAPER CLASSIFICATION
# =========================================================

def is_excluded(text):

    value = text.lower()

    return any(
        term in value
        for term in EXCLUDED_TERMS
    )


def detect_stage(text, year):

    value = text.lower()

    if "screening" in value:
        return "Screening"

    if "mains" in value or "main paper" in value:
        return "Mains"

    matches = re.findall(
        r"\bpaper\s*[-_ ]?([12])\b",
        value
    )

    if len(set(matches)) == 1:
        return f"Paper {matches[0]}"

    if year <= 2006:
        return "IIT-JEE Paper"

    return ""


def detect_language(text):

    value = text.lower()

    if "hindi" in value:
        return "Hindi"

    if "english" in value:
        return "English"

    return "English"


# =========================================================
# RECORD CREATION
# =========================================================

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

    if not is_official_url(url):
        return None

    if stage not in ("Paper 1", "Paper 2"):
        return None

    exam_name = (
        "JEE Advanced"
        if year >= 2013
        else "IIT-JEE"
    )

    if not organizing_institute:
        organizing_institute = (
            ORGANIZING_INSTITUTES.get(year, "")
        )

    if not exam_date:
        exam_date = EXAM_DATES.get(year, "")

    return {
        "year": year,
        "exam_date": exam_date,
        "paper_type": stage,
        "language": language,
        "document_type": "Question Paper",
        "title": (
            f"{exam_name} {year} "
            f"{stage} ({language})"
        ),
        "source_url": url,
        "download_url": url,
        "storage_path": "",
        "download_mode": "official_external",
        "source_page": page,
        "source_authority": authority,
        "source_type": "official",
        "source_label": "JEE Advanced Official Website",
        "verification_status": status,
        "exam_name": exam_name,
        "stage": stage,
        "organizing_institute": organizing_institute,
        "exam_session": ""
    }


# =========================================================
# OFFICIAL ARCHIVE DISCOVERY: 2007–2025
# =========================================================
def discover_official_papers():

    soup = fetch_soup(ARCHIVE_URL)

    if soup is None:
        return []

    records = []
    seen = set()

    pdf_pattern = re.compile(
        r"(?P<year>20\d{2})[_-]"
        r"(?P<paper>[12])"
        r"(?:[_-](?P<language>English|Hindi))?"
        r"\.pdf$",
        re.IGNORECASE
    )

    for anchor in soup.find_all("a", href=True):

        href = urljoin(
            ARCHIVE_URL,
            anchor["href"]
        )

        if not is_official_url(href):
            continue

        filename = urlparse(href).path.rsplit(
            "/",
            1
        )[-1]

        match = pdf_pattern.fullmatch(filename)

        if not match:
            continue

        year = int(match.group("year"))

        if year < 2007 or year > 2025:
            continue

        paper_number = match.group("paper")

        language = (
            match.group("language") or "English"
        ).capitalize()

        stage = f"Paper {paper_number}"

        if href in seen:
            continue

        seen.add(href)

        record = make_record(
            year=year,
            stage=stage,
            language=language,
            url=href,
            page=ARCHIVE_URL,
            authority="JEE Advanced Official",
            status="official_source_link",
            organizing_institute=(
                ORGANIZING_INSTITUTES.get(year, "")
            )
        )

        if record:
            records.append(record)

    return records


# =========================================================
# CURRENT OFFICIAL WEBSITE DISCOVERY
# =========================================================

def discover_current_official_papers():

    soup = fetch_soup(OFFICIAL_URL)

    if soup is None:
        return []

    page_text = soup.get_text(" ", strip=True)

    year_matches = re.findall(
        r"JEE\s+Advanced\s+(20\d{2})",
        page_text,
        flags=re.IGNORECASE
    )

    if not year_matches:
        return []

    year = max(
        int(value)
        for value in year_matches
    )

    if year < 2007:
        return []

    institute = detect_organizing_institute(
        year=year,
        soup=soup,
        page_url=OFFICIAL_URL
    )

    records = []
    seen = set()

    for anchor in soup.find_all("a", href=True):

        href = urljoin(
            OFFICIAL_URL,
            anchor["href"]
        )

        if not is_official_url(href):
            continue

        filename = urlparse(href).path.rsplit(
            "/",
            1
        )[-1].lower()

        match = re.fullmatch(
            r"p([12])_(english|hindi)\.pdf",
            filename
        )

        if not match:
            continue

        if href in seen:
            continue

        seen.add(href)

        paper_number = match.group(1)
        language = match.group(2).capitalize()

        record = make_record(
            year=year,
            stage=f"Paper {paper_number}",
            language=language,
            url=href,
            page=OFFICIAL_URL,
            authority="JEE Advanced Official",
            status="official_source_link",
            exam_date=EXAM_DATES.get(year, ""),
            organizing_institute=institute
        )

        if record:
            records.append(record)

    return records


# =========================================================
# MAIN DISCOVERY FUNCTION
# =========================================================

def discover_jee_advanced_papers():

    records = []

    records.extend(
        discover_official_papers()
    )

    records.extend(
        discover_current_official_papers()
    )

    unique_records = {}

    for record in records:
        unique_records[record["source_url"]] = record

    return list(unique_records.values())


# =========================================================
# DATABASE SYNCHRONIZATION
# =========================================================

def sync_jee_advanced_papers():

    records = discover_jee_advanced_papers()

    if not records:
        return {
            "success": False,
            "message": (
                "No official JEE Advanced PDF links found."
            ),
            "discovered": 0,
            "synced": 0
        }

    from app import connect

    synced = 0

    with connect() as db:

        with db.cursor() as cur:

            for record in records:

                now = int(time.time())

                cur.execute(
                    """
                    INSERT INTO jee_advanced_papers (
                        year,
                        exam_date,
                        paper_type,
                        language,
                        document_type,
                        title,
                        source_url,
                        source_page,
                        source_authority,
                        source_type,
                        source_label,
                        verification_status,
                        created_at,
                        updated_at,
                        exam_name,
                        stage,
                        organizing_institute,
                        exam_session,
                        download_url,
                        storage_path,
                        download_mode
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (source_url)
                    DO UPDATE SET
                        year = EXCLUDED.year,
                        exam_date = EXCLUDED.exam_date,
                        paper_type = EXCLUDED.paper_type,
                        language = EXCLUDED.language,
                        document_type = EXCLUDED.document_type,
                        title = EXCLUDED.title,
                        source_page = EXCLUDED.source_page,
                        source_authority = EXCLUDED.source_authority,
                        source_type = EXCLUDED.source_type,
                        source_label = EXCLUDED.source_label,
                        verification_status = EXCLUDED.verification_status,
                        exam_name = EXCLUDED.exam_name,
                        stage = EXCLUDED.stage,
                        exam_session = EXCLUDED.exam_session,

                        organizing_institute =
                            CASE
                                WHEN EXCLUDED.organizing_institute <> ''
                                THEN EXCLUDED.organizing_institute
                                ELSE jee_advanced_papers.organizing_institute
                            END,

                        download_url = EXCLUDED.download_url,
                        download_mode = EXCLUDED.download_mode,

                        storage_path =
                            CASE
                                WHEN EXCLUDED.storage_path <> ''
                                THEN EXCLUDED.storage_path
                                ELSE jee_advanced_papers.storage_path
                            END,

                        updated_at = EXCLUDED.updated_at
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
                        record["source_type"],
                        record["source_label"],
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

                synced += 1

    return {
        "success": True,
        "message": (
            "JEE Advanced official paper sync completed."
        ),
        "discovered": len(records),
        "synced": synced
    }
