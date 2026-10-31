
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# NEET / AIPMT HISTORICAL QUESTION PAPER DISCOVERY
# ============================================================

# NTA is the primary source.
# Third-party sources are used only to discover additional papers.
# Their records are always labelled third_party.

SOURCES = [
    {
        "name": "NTA",
        "url": "https://neet.nta.nic.in/archive/",
        "authority": "NTA",
        "type": "official",
        "priority": 1,
    },
    {
        "name": "AglaSem",
        "url": "https://docs.aglasem.com/",
        "authority": "AglaSem",
        "type": "third_party",
        "priority": 2,
    },
    {
        "name": "ExamGOAL",
        "url": "https://examgoal.com/",
        "authority": "ExamGOAL",
        "type": "third_party",
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
MAX_CHILD_PAGES_PER_SOURCE = 80
REQUEST_DELAY = 0.25

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Only these domains are allowed for the corresponding sources.
SOURCE_HOSTS = {
    "NTA": {
        "neet.nta.nic.in",
        "nta.ac.in",
        "cdnbbsr.s3waas.gov.in",
    },
    "AglaSem": {
        "aglasem.com",
        "www.aglasem.com",
        "docs.aglasem.com",
    },
    "ExamGOAL": {
        "examgoal.com",
        "www.examgoal.com",
        "pdf.questions.examgoal.com",
    },
}

EXCLUDED_TERMS = [
    "answer key",
    "answer keys",
    "final answer",
    "provisional answer",
    "solution",
    "solutions",
    "response sheet",
    "omr",
    "admit card",
    "information bulletin",
    "eligibility criteria",
    "examination schedule",
    "exam schedule",
    "syllabus",
    "brochure",
    "result",
    "score card",
    "notification",
    "public notice",
    "faq",
    "cutoff",
    "cut off",
    "mock test",
    "sample paper",
    "registration",
    "application form",
    "invitation",
    "press release",
    "correction window",
]

QUESTION_PAPER_TERMS = [
    "question paper",
    "question papers",
    "question booklet",
    "question book",
    "neet qp",
    "aipmt qp",
    "qp paper",
    "previous year paper",
    "previous years paper",
    "past year paper",
]

LANGUAGE_RULES = [
    ("English & Hindi", ["english & hindi", "eng & hindi", "english and hindi"]),
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


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def host_of(url):
    return (urlparse(url).hostname or "").lower()


def is_allowed_host(url, source_name):
    parsed = urlparse(url)

    if parsed.scheme != "https":
        return False

    host = host_of(url)

    return host in SOURCE_HOSTS.get(source_name, set())


def fetch_page(url, source_name):
    if not is_allowed_host(url, source_name):
        return None

    try:
        response = SESSION.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        if not is_allowed_host(response.url, source_name):
            print(f"[BLOCKED REDIRECT] {url}")
            return None

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        if "text/html" not in content_type and "application/xhtml" not in content_type:
            return None

        return response

    except requests.RequestException as exc:
        print(f"[PAGE ERROR] {url}: {exc}")
        return None


def is_excluded(text):
    text = clean_text(text).lower()

    return any(term in text for term in EXCLUDED_TERMS)


def get_year(text):
    if not text:
        return None

    matches = re.findall(r"\b(19\d{2}|20\d{2})\b", text)

    for value in matches:
        year = int(value)

        if 1988 <= year <= 2026:
            return year

    return None


def get_language(text):
    text = clean_text(text).lower()

    for language, terms in LANGUAGE_RULES:
        if any(term in text for term in terms):
            return language

    return "Unknown"


def get_exam_code(text):
    patterns = [
        r"\bset\s*([A-Z0-9]{1,4})\b",
        r"\bcode\s*([A-Z0-9]{1,5})\b",
        r"\bbooklet\s*([A-Z0-9]{1,5})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.I)

        if match:
            return match.group(1).upper()

    return ""


def get_exam_name(year, text):
    text = clean_text(text).lower()

    if "aipmt" in text or (year and year < 2013):
        return "AIPMT"

    return "NEET UG"


def get_exam_session(text):
    text = clean_text(text).lower()

    if any(term in text for term in [
        "re-exam", "re exam", "retest", "re-test", "reneet"
    ]):
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


# ============================================================
# STRICT QUESTION PAPER VALIDATION
# ============================================================

def is_actual_question_paper(title, context=""):
    """
    A record must contain:
    - NEET or AIPMT identification
    - Explicit question-paper evidence
    - No excluded document terms
    """

    combined = clean_text(f"{title} {context}")
    text = combined.lower()

    if not text or is_excluded(text):
        return False

    exam_found = bool(
        re.search(r"\bneet\b", text)
        or re.search(r"\baipmt\b", text)
    )

    paper_found = any(
        term in text
        for term in QUESTION_PAPER_TERMS
    )

    # NTA archive sometimes uses labels like:
    # "English Set E1 NEET QP 2020"
    if re.search(r"\bneet\s+qp\b", text):
        paper_found = True

    if re.search(r"\baipmt\s+qp\b", text):
        paper_found = True

    return exam_found and paper_found


# ============================================================
# PDF VALIDATION
# ============================================================

def is_direct_pdf_url(url):
    if not url:
        return False

    parsed = urlparse(url)

    if parsed.scheme != "https":
        return False

    return (
        parsed.path.lower().endswith(".pdf")
        or ".pdf" in parsed.path.lower()
    )


def verify_pdf(url, source_name):
    """
    Checks whether the URL actually returns PDF bytes.
    Does not download the entire file.
    """

    if not is_allowed_host(url, source_name):
        return False

    try:
        response = SESSION.get(
            url,
            headers={"Range": "bytes=0-7"},
            timeout=TIMEOUT,
            allow_redirects=True,
            stream=True,
        )

        if not is_allowed_host(response.url, source_name):
            response.close()
            return False

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        first_bytes = response.raw.read(8)
        response.close()

        return (
            first_bytes.startswith(b"%PDF-")
            or "application/pdf" in content_type
        )

    except requests.RequestException as exc:
        print(f"[PDF CHECK ERROR] {url}: {exc}")
        return False


# ============================================================
# DATABASE RECORD
# ============================================================

def make_record(
    title,
    pdf_url,
    source_page,
    source_name,
    authority,
    source_type,
    context="",
):
    title = clean_text(title)
    context = clean_text(context)

    combined_text = clean_text(f"{title} {context}")

    if not is_actual_question_paper(title, context):
        return None

    if not is_direct_pdf_url(pdf_url):
        return None

    if not is_allowed_host(pdf_url, source_name):
        return None

    year = get_year(combined_text)

    if not year:
        return None

    if not verify_pdf(pdf_url, source_name):
        print(f"[NOT A VERIFIED PDF] {pdf_url}")
        return None

    official = source_type == "official"

    return {
        "year": year,
        "exam_date": "",
        "paper_type": "Question Paper",
        "language": get_language(combined_text),
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
            "official_pdf_verified"
            if official
            else "third_party_pdf_verified"
        ),
        "created_at": int(time.time()),
        "updated_at": int(time.time()),
        "exam_name": get_exam_name(year, combined_text),
        "exam_session": get_exam_session(combined_text),
        "exam_code": get_exam_code(combined_text),
        "download_url": pdf_url,
        "storage_path": "",
        "download_mode": (
            "official_external"
            if official
            else "external"
        ),
    }


# ============================================================
# NTA ARCHIVE
# ============================================================

def discover_nta():
    records = []
    source = SOURCES[0]

    response = fetch_page(source["url"], source["name"])

    if not response:
        print("[NTA] Archive could not be accessed.")
        return records

    soup = BeautifulSoup(response.text, "html.parser")

    # First inspect table rows. This captures title and PDF link
    # from the same archive entry.
    for row in soup.find_all("tr"):
        row_text = clean_text(row.get_text(" ", strip=True))

        if not is_actual_question_paper(row_text):
            continue

        for anchor in row.find_all("a", href=True):
            pdf_url = urljoin(source["url"], anchor["href"])

            if not is_direct_pdf_url(pdf_url):
                continue

            record = make_record(
                title=row_text,
                pdf_url=pdf_url,
                source_page=source["url"],
                source_name=source["name"],
                authority=source["authority"],
                source_type=source["type"],
                context=row_text,
            )

            if record:
                records.append(record)

    # Also inspect non-table archive entries.
    for anchor in soup.find_all("a", href=True):
        pdf_url = urljoin(source["url"], anchor["href"])

        if not is_direct_pdf_url(pdf_url):
            continue

        anchor_text = clean_text(
            anchor.get_text(" ", strip=True)
        )

        parent_text = clean_text(
            anchor.parent.get_text(" ", strip=True)
        )

        context = clean_text(f"{anchor_text} {parent_text}")

        if not is_actual_question_paper(anchor_text, context):
            continue

        record = make_record(
            title=context,
            pdf_url=pdf_url,
            source_page=source["url"],
            source_name=source["name"],
            authority=source["authority"],
            source_type=source["type"],
            context=context,
        )

        if record:
            records.append(record)

    return records


# ============================================================
# THIRD-PARTY SOURCE CRAWLER
# ============================================================

def discover_third_party(source):
    records = []

    source_name = source["name"]
    start_url = source["url"]

    response = fetch_page(start_url, source_name)

    if not response:
        print(f"[{source_name}] Source page unavailable.")
        return records

    soup = BeautifulSoup(response.text, "html.parser")

    visited_pages = set()
    candidate_pages = set()

    # Find relevant NEET/AIPMT paper pages.
    for anchor in soup.find_all("a", href=True):
        href = urljoin(start_url, anchor["href"])
        anchor_text = clean_text(
            anchor.get_text(" ", strip=True)
        )

        if not is_allowed_host(href, source_name):
            continue

        if is_direct_pdf_url(href):
            continue

        context = clean_text(
            f"{anchor_text} {anchor.parent.get_text(' ', strip=True)}"
        )

        if is_excluded(context):
            continue

        year = get_year(context)

        has_exam = bool(
            re.search(r"\bneet\b|\baipmt\b", context, re.I)
        )

        has_paper_term = any(
            term in context.lower()
            for term in QUESTION_PAPER_TERMS
        )

        if year and has_exam and has_paper_term:
            candidate_pages.add(href)

    # Inspect relevant paper pages.
    for page_url in list(candidate_pages)[:MAX_CHILD_PAGES_PER_SOURCE]:
        if page_url in visited_pages:
            continue

        visited_pages.add(page_url)

        page_response = fetch_page(page_url, source_name)

        if not page_response:
            continue

        page_soup = BeautifulSoup(
            page_response.text,
            "html.parser",
        )

        page_title = clean_text(
            page_soup.title.get_text(" ", strip=True)
            if page_soup.title
            else ""
        )

        page_text = clean_text(
            page_soup.get_text(" ", strip=True)
        )

        page_context = clean_text(
            f"{page_title} {page_text[:2500]}"
        )

        if is_excluded(page_title):
            continue

        if not is_actual_question_paper(page_title, page_context):
            continue

        for anchor in page_soup.find_all("a", href=True):
            pdf_url = urljoin(page_url, anchor["href"])

            if not is_direct_pdf_url(pdf_url):
                continue

            link_text = clean_text(
                anchor.get_text(" ", strip=True)
            )

            record = make_record(
                title=page_title or link_text,
                pdf_url=pdf_url,
                source_page=page_url,
                source_name=source_name,
                authority=source["authority"],
                source_type=source["type"],
                context=page_context,
            )

            if record:
                records.append(record)

        time.sleep(REQUEST_DELAY)

    # Also inspect direct PDFs linked on the original catalogue.
    for anchor in soup.find_all("a", href=True):
        pdf_url = urljoin(start_url, anchor["href"])

        if not is_direct_pdf_url(pdf_url):
            continue

        link_text = clean_text(
            anchor.get_text(" ", strip=True)
        )

        context = clean_text(
            f"{link_text} {anchor.parent.get_text(' ', strip=True)}"
        )

        record = make_record(
            title=context,
            pdf_url=pdf_url,
            source_page=start_url,
            source_name=source_name,
            authority=source["authority"],
            source_type=source["type"],
            context=context,
        )

        if record:
            records.append(record)

    return records


# ============================================================
# MASTER DISCOVERY
# ============================================================

def discover_neet_papers():
    all_records = []

    # NTA first.
    print("\n========== NTA SEARCH ==========")

    try:
        nta_records = discover_nta()
        print(f"[NTA] Valid papers: {len(nta_records)}")
        all_records.extend(nta_records)
    except Exception as exc:
        print(f"[NTA ERROR] {exc}")

    # Third-party sources.
    for source in SOURCES:
        if source["type"] != "third_party":
            continue

        print(f"\n========== {source['name']} SEARCH ==========")

        try:
            found = discover_third_party(source)
            print(f"[{source['name']}] Valid papers: {len(found)}")
            all_records.extend(found)
        except Exception as exc:
            print(f"[{source['name']} ERROR] {exc}")

    # Deduplicate by URL.
    unique = {}

    for record in all_records:
        url = record["source_url"].split("#")[0]

        existing = unique.get(url)

        if existing is None:
            unique[url] = record

        elif record["source_type"] == "official":
            unique[url] = record

    results = list(unique.values())

    # Official records first, then newest years.
    results.sort(
        key=lambda item: (
            item["source_type"] != "official",
            -item["year"],
            item["language"],
            item["exam_code"],
        )
    )

    print("\n========== DISCOVERY SUMMARY ==========")
    print(f"Total unique papers: {len(results)}")

    print(
        "Official NTA papers:",
        sum(r["source_type"] == "official" for r in results),
    )

    print(
        "Third-party papers:",
        sum(r["source_type"] == "third_party" for r in results),
    )

    print("\nYear-wise distribution:")

    year_counts = {}

    for record in results:
        year_counts[record["year"]] = (
            year_counts.get(record["year"], 0) + 1
        )

    for year in sorted(year_counts):
        print(f"{year}: {year_counts[year]}")

    return results


# ============================================================
# DATABASE SYNC
# ============================================================

def sync_neet_papers():
    from app import connect

    records = discover_neet_papers()

    if not records:
        return {
            "success": False,
            "message": "No verified question papers found. Database unchanged.",
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

    placeholders = ", ".join(["%s"] * len(columns))

    sql = f"""
        INSERT INTO public.neet_papers (
            {", ".join(columns)}
        )
        VALUES ({placeholders})
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

        official_count = sum(
            record["source_type"] == "official"
            for record in records
        )

        third_party_count = sum(
            record["source_type"] == "third_party"
            for record in records
        )

        return {
            "success": True,
            "discovered": len(records),
            "inserted_or_updated": len(records),
            "official_records": official_count,
            "third_party_records": third_party_count,
            "message": "NEET paper sync completed.",
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
