
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# --------------------------------------------------
# SOURCE CONFIGURATION
# --------------------------------------------------

SOURCES = [
    {
        "name": "NTA",
        "url": "https://neet.nta.nic.in/archive/",
        "authority": "NTA",
        "priority": 1,
    },
    {
        "name": "AglaSem",
        "url": "https://docs.aglasem.com/org/nta/neet-ug/question-paper",
        "authority": "AglaSem",
        "priority": 2,
    },
    {
        "name": "ExamGOAL",
        "url": "https://pdf.questions.examgoal.com/past-years/year-wise/medical/neet",
        "authority": "ExamGOAL",
        "priority": 3,
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    )
}

TIMEOUT = 25
MAX_CHILD_PAGES = 100

EXCLUDED_TERMS = (
    "answer key",
    "answer keys",
    "solution",
    "solutions",
    "response sheet",
    "omr",
    "admit card",
    "information bulletin",
    "syllabus",
    "brochure",
    "result",
    "score card",
    "notification",
    "public notice",
    "faq",
    "cutoff",
    "mock test",
    "sample paper",
)

LANGUAGES = [
    "English",
    "Hindi",
    "English & Hindi",
    "Assamese",
    "Bengali",
    "Gujarati",
    "Kannada",
    "Malayalam",
    "Marathi",
    "Odia",
    "Punjabi",
    "Tamil",
    "Telugu",
    "Urdu",
]


# --------------------------------------------------
# HTTP HELPERS
# --------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch(url):
    try:
        response = SESSION.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response
    except requests.RequestException as exc:
        print(f"[FETCH ERROR] {url}: {exc}")
        return None


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def is_pdf_url(url):
    if not url:
        return False

    parsed = urlparse(url)
    path = parsed.path.lower()

    return (
        parsed.scheme == "https"
        and (
            path.endswith(".pdf")
            or ".pdf?" in url.lower()
        )
    )


def is_excluded(text):
    text = text.lower()
    return any(term in text for term in EXCLUDED_TERMS)


def get_year(text):
    match = re.search(r"\b(19\d{2}|20\d{2})\b", text or "")
    if match:
        year = int(match.group(1))
        if 1988 <= year <= 2026:
            return year
    return None


def get_language(text):
    text = (text or "").lower()

    checks = [
        ("English & Hindi", ["english & hindi", "eng & hindi", "english hindi"]),
        ("Assamese", ["assamese"]),
        ("Bengali", ["bengali"]),
        ("Gujarati", ["gujarati"]),
        ("Kannada", ["kannada", "kanada"]),
        ("Malayalam", ["malayalam"]),
        ("Marathi", ["marathi"]),
        ("Odia", ["odia", "oriya"]),
        ("Punjabi", ["punjabi"]),
        ("Tamil", ["tamil"]),
        ("Telugu", ["telugu"]),
        ("Urdu", ["urdu"]),
        ("Hindi", ["hindi"]),
        ("English", ["english", "eng"]),
    ]

    for language, words in checks:
        if any(word in text for word in words):
            return language

    return "Unknown"


def get_exam_name(year, text):
    text = (text or "").lower()

    if "aipmt" in text or (year and year < 2013):
        return "AIPMT"

    return "NEET UG"


def get_exam_session(text):
    text = (text or "").lower()

    if "re-exam" in text or "re exam" in text or "reneet" in text:
        return "Re-Examination"

    if "manipur" in text:
        return "Manipur"

    if "phase 2" in text:
        return "Phase 2"

    if "phase 1" in text:
        return "Phase 1"

    if "odisha" in text:
        return "Odisha"

    return "Main Examination"


def get_exam_code(text):
    patterns = [
        r"\bset\s*([A-Z0-9]{1,4})\b",
        r"\bcode\s*([A-Z0-9]{1,5})\b",
        r"\b([A-Z]\d)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text or "", re.I)
        if match:
            return match.group(1).upper()

    return ""


# --------------------------------------------------
# RECORD CREATION
# --------------------------------------------------

def make_record(title, pdf_url, source_page, source_name, authority):
    title = clean_text(title)
    year = get_year(title)

    if not year or not is_pdf_url(pdf_url):
        return None

    if is_excluded(title):
        return None

    language = get_language(title)
    exam_name = get_exam_name(year, title)

    official = authority == "NTA"

    return {
        "year": year,
        "exam_date": "",
        "paper_type": "Question Paper",
        "language": language,
        "document_type": "Question Paper",
        "title": title,
        "source_url": pdf_url,
        "source_page": source_page,
        "source_authority": authority,
        "source_type": "official" if official else "third_party",
        "source_label": (
            "Official NTA PDF"
            if official
            else f"Third-party copy ({source_name})"
        ),
        "verification_status": (
            "official_source"
            if official
            else "source_page_found"
        ),
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
        "exam_name": exam_name,
        "exam_session": get_exam_session(title),
        "exam_code": get_exam_code(title),
        "download_url": pdf_url,
        "storage_path": "",
        "download_mode": "official_external" if official else "external",
    }


# --------------------------------------------------
# NTA ARCHIVE DISCOVERY
# --------------------------------------------------

def discover_nta():
    records = []

    source = SOURCES[0]
    response = fetch(source["url"])

    if not response:
        return records

    soup = BeautifulSoup(response.text, "html.parser")

    for row in soup.find_all("tr"):
        row_text = clean_text(row.get_text(" ", strip=True))

        if is_excluded(row_text):
            continue

        for anchor in row.find_all("a", href=True):
            pdf_url = urljoin(source["url"], anchor["href"])

            if not is_pdf_url(pdf_url):
                continue

            title = row_text or clean_text(anchor.get_text(" ", strip=True))

            record = make_record(
                title,
                pdf_url,
                source["url"],
                source["name"],
                source["authority"],
            )

            if record:
                records.append(record)

    # Fallback for archive pages not using table rows
    if not records:
        for anchor in soup.find_all("a", href=True):
            title = clean_text(anchor.get_text(" ", strip=True))
            pdf_url = urljoin(source["url"], anchor["href"])

            if not is_pdf_url(pdf_url):
                continue

            record = make_record(
                title,
                pdf_url,
                source["url"],
                source["name"],
                source["authority"],
            )

            if record:
                records.append(record)

    return records


# --------------------------------------------------
# AGALSEM DISCOVERY
# --------------------------------------------------

def discover_aglasem():
    records = []
    source = SOURCES[1]

    response = fetch(source["url"])
    if not response:
        return records

    soup = BeautifulSoup(response.text, "html.parser")

    child_pages = set()

    for anchor in soup.find_all("a", href=True):
        title = clean_text(anchor.get_text(" ", strip=True))
        href = urljoin(source["url"], anchor["href"])

        if (
            "docs.aglasem.com" in urlparse(href).netloc
            and "/view/" in href
            and "neet" in title.lower()
            and "question paper" in title.lower()
        ):
            child_pages.add((title, href))

    for title, page_url in list(child_pages)[:MAX_CHILD_PAGES]:
        page_response = fetch(page_url)

        if not page_response:
            continue

        page_soup = BeautifulSoup(
            page_response.text,
            "html.parser",
        )

        page_title = clean_text(
            page_soup.title.get_text(" ", strip=True)
            if page_soup.title
            else title
        )

        page_text = clean_text(
            page_soup.get_text(" ", strip=True)
        )

        if is_excluded(page_title):
            continue

        for anchor in page_soup.find_all("a", href=True):
            link_text = clean_text(
                anchor.get_text(" ", strip=True)
            )

            if "download" not in link_text.lower():
                continue

            pdf_url = urljoin(page_url, anchor["href"])

            # Download endpoints may redirect or require login.
            # Only store direct PDF URLs here.
            if not is_pdf_url(pdf_url):
                continue

            record = make_record(
                page_title,
                pdf_url,
                page_url,
                source["name"],
                source["authority"],
            )

            if record:
                records.append(record)

        time.sleep(0.3)

    return records


# --------------------------------------------------
# EXAMGOAL DISCOVERY
# --------------------------------------------------

def discover_examgoal():
    records = []
    source = SOURCES[2]

    response = fetch(source["url"])
    if not response:
        return records

    soup = BeautifulSoup(response.text, "html.parser")

    year_pages = set()

    for anchor in soup.find_all("a", href=True):
        href = urljoin(source["url"], anchor["href"])
        title = clean_text(anchor.get_text(" ", strip=True))

        if re.search(r"/neet-(19\d{2}|20\d{2})/?$", href):
            year_pages.add(href)

    for page_url in sorted(year_pages):
        page_response = fetch(page_url)

        if not page_response:
            continue

        page_soup = BeautifulSoup(
            page_response.text,
            "html.parser",
        )

        page_title = clean_text(
            page_soup.title.get_text(" ", strip=True)
            if page_soup.title
            else page_url.rsplit("/", 1)[-1]
        )

        if is_excluded(page_title):
            continue

        for anchor in page_soup.find_all("a", href=True):
            link_text = clean_text(
                anchor.get_text(" ", strip=True)
            )

            pdf_url = urljoin(page_url, anchor["href"])

            if not is_pdf_url(pdf_url):
                continue

            title = f"{page_title} {link_text}"

            if is_excluded(title):
                continue

            record = make_record(
                title,
                pdf_url,
                page_url,
                source["name"],
                source["authority"],
            )

            if record:
                records.append(record)

        time.sleep(0.3)

    return records


# --------------------------------------------------
# MASTER DISCOVERY
# --------------------------------------------------

def discover_neet_papers():
    all_records = []

    discoverers = [
        ("NTA", discover_nta),
        ("AglaSem", discover_aglasem),
        ("ExamGOAL", discover_examgoal),
    ]

    for source_name, discoverer in discoverers:
        print(f"[NEET] Searching {source_name}...")

        try:
            found = discoverer()
            print(f"[NEET] {source_name}: {len(found)} records")
            all_records.extend(found)

        except Exception as exc:
            print(f"[NEET ERROR] {source_name}: {exc}")

    # Deduplicate by URL
    unique = {}

    for record in all_records:
        url = record["source_url"].split("#")[0]
        if url not in unique:
            unique[url] = record
        elif record["source_type"] == "official":
            unique[url] = record

    # Sort official first, then year descending
    results = list(unique.values())

    results.sort(
        key=lambda item: (
            item["source_type"] != "official",
            -item["year"],
            item["language"],
        )
    )

    print(f"[NEET] Total unique records: {len(results)}")

    return results


# --------------------------------------------------
# DATABASE SYNC
# --------------------------------------------------

def sync_neet_papers():
    from app import connect

    records = discover_neet_papers()

    if not records:
        return {
            "success": False,
            "message": "No papers discovered. Database was not changed.",
            "discovered": 0,
            "inserted_or_updated": 0,
        }

    columns = [
        "year",
        "exam_date",
        "paper_type",
        "language",
        "document_type",
        "title",
        "source_url",
        "source_page",
        "source_authority",
        "source_type",
        "source_label",
        "verification_status",
        "created_at",
        "updated_at",
        "exam_name",
        "exam_session",
        "exam_code",
        "download_url",
        "storage_path",
        "download_mode",
    ]

    sql = f"""
        INSERT INTO public.neet_papers ({", ".join(columns)})
        VALUES ({", ".join(["%s"] * len(columns))})
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
            updated_at = EXCLUDED.updated_at,
            exam_name = EXCLUDED.exam_name,
            exam_session = EXCLUDED.exam_session,
            exam_code = EXCLUDED.exam_code,
            download_url = EXCLUDED.download_url,
            download_mode = EXCLUDED.download_mode
    """

    values = [
        tuple(record.get(column, "") for column in columns)
        for record in records
    ]

    connection = connect()

    try:
        with connection.cursor() as cursor:
            cursor.executemany(sql, values)

        connection.commit()

        return {
            "success": True,
            "discovered": len(records),
            "inserted_or_updated": len(records),
            "official_records": sum(
                r["source_type"] == "official"
                for r in records
            ),
            "third_party_records": sum(
                r["source_type"] == "third_party"
                for r in records
            ),
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
