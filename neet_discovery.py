
import re
import time
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

START_YEAR = 2007
END_YEAR = 2026

NTA_ARCHIVE = "https://neet.nta.nic.in/archive/"

AGLASEM_ARCHIVE = (
    "https://docs.aglasem.com/org/nta/neet-ug/question-paper"
)

EXAMGOAL_ARCHIVE = (
    "https://pdf.questions.examgoal.com/"
    "past-years/year-wise/medical/neet"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    )
}

TIMEOUT = 25
MAX_DETAIL_PAGES = 150
REQUEST_DELAY = 0.2

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Hostnames allowed for each source and its known PDF CDN.
ALLOWED_HOSTS = {
    "NTA": {
        "neet.nta.nic.in",
        "nta.ac.in",
        "cdnbbsr.s3waas.gov.in",
    },
    "AglaSem": {
        "aglasem.com",
        "www.aglasem.com",
        "docs.aglasem.com",
        "admission.aglasem.com",
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

PAPER_TERMS = [
    "question paper",
    "question papers",
    "question booklet",
    "question book",
    "neet qp",
    "aipmt qp",
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


def get_host(url):
    return (urlparse(url).hostname or "").lower()


def allowed_url(url, source):
    parsed = urlparse(url)

    return (
        parsed.scheme == "https"
        and get_host(url) in ALLOWED_HOSTS.get(source, set())
    )


def normalise_url(url):
    url, _ = urldefrag(url)
    return url.strip()


def get_year(text):
    if not text:
        return None

    matches = re.findall(
        r"\b(200[7-9]|201\d|202[0-6])\b",
        text,
        re.I,
    )

    if not matches:
        return None

    return int(matches[0])


def is_excluded(text):
    text = clean_text(text).lower()

    return any(term in text for term in EXCLUDED_TERMS)


def has_exam_name(text):
    return bool(
        re.search(r"\bneet\b|\baipmt\b", text or "", re.I)
    )


def has_question_paper_term(text):
    text = clean_text(text).lower()

    if "neet qp" in text or "aipmt qp" in text:
        return True

    return any(term in text for term in PAPER_TERMS)


def is_actual_question_paper(title, context=""):
    text = clean_text(f"{title} {context}")

    if not text or is_excluded(text):
        return False

    return (
        has_exam_name(text)
        and has_question_paper_term(text)
    )


def get_language(text):
    text = clean_text(text).lower()

    for language, terms in LANGUAGE_RULES:
        if any(term in text for term in terms):
            return language

    return "Unknown"


def get_exam_name(year, text):
    text = clean_text(text).lower()

    if "aipmt" in text or (year and year <= 2015):
        return "AIPMT"

    return "NEET UG"


def get_exam_session(text):
    text = clean_text(text).lower()

    if any(term in text for term in [
        "re-neet",
        "re neet",
        "re-exam",
        "re exam",
        "re-examination",
        "re examination",
        "retest",
    ]):
        return "Re-Examination"

    if "cancelled" in text or "canceled" in text:
        return "Cancelled Examination"

    if "manipur" in text:
        return "Manipur"

    if "phase 2" in text or "phase-2" in text:
        return "Phase 2"

    if "phase 1" in text or "phase-1" in text:
        return "Phase 1"

    if "odisha" in text:
        return "Odisha"

    if "karnataka" in text:
        return "Karnataka"

    if "prelims" in text or "preliminary" in text:
        return "Preliminary"

    if "mains" in text:
        return "Mains"

    return "Main Examination"


def get_exam_code(text):
    patterns = [
        r"\bset\s*([A-Z0-9]{1,4})\b",
        r"\bcode\s*([A-Z0-9]{1,5})\b",
        r"\bbooklet\s*([A-Z0-9]{1,5})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text or "", re.I)

        if match:
            return match.group(1).upper()

    return ""


# ============================================================
# HTTP HELPERS
# ============================================================

def fetch_html(url, source):
    if not allowed_url(url, source):
        return None

    try:
        response = SESSION.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        if not allowed_url(response.url, source):
            print("[BLOCKED REDIRECT]", response.url)
            return None

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        if "html" not in content_type:
            return None

        return BeautifulSoup(response.text, "html.parser")

    except requests.RequestException as exc:
        print(f"[HTML ERROR] {url}: {exc}")
        return None


def is_pdf_url(url):
    if not url:
        return False

    path = urlparse(url).path.lower()

    return (
        path.endswith(".pdf")
        or path.endswith(".pdf/")
    )


def verify_pdf(url, source):
    """
    Check the PDF header using a small ranged request.
    This avoids downloading the complete PDF during discovery.
    """

    if not allowed_url(url, source):
        return False

    try:
        response = SESSION.get(
            url,
            headers={"Range": "bytes=0-7"},
            timeout=TIMEOUT,
            allow_redirects=True,
            stream=True,
        )

        if not allowed_url(response.url, source):
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
# RECORD CREATION
# ============================================================

def make_record(
    title,
    pdf_url,
    source_page,
    source_name,
    source_type,
    context="",
):
    title = clean_text(title)
    context = clean_text(context)

    combined = clean_text(f"{title} {context}")

    if not is_actual_question_paper(title, context):
        return None

    year = get_year(combined)

    if not year or not START_YEAR <= year <= END_YEAR:
        return None

    if not is_pdf_url(pdf_url):
        return None

    if not allowed_url(pdf_url, source_name):
        return None

    if not verify_pdf(pdf_url, source_name):
        print("[INVALID PDF]", pdf_url)
        return None

    official = source_type == "official"

    return {
        "year": year,
        "exam_date": "",
        "paper_type": "Question Paper",
        "language": get_language(combined),
        "document_type": "Question Paper",
        "title": title,
        "source_url": pdf_url,
        "source_page": source_page,
        "source_authority": (
            "NTA" if official else source_name
        ),
        "source_type": (
            "official" if official else "third_party"
        ),
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
        "exam_name": get_exam_name(year, combined),
        "exam_session": get_exam_session(combined),
        "exam_code": get_exam_code(combined),
        "download_url": pdf_url,
        "storage_path": "",
        "download_mode": (
            "official_external" if official else "external"
        ),
    }


# ============================================================
# NTA ARCHIVE DISCOVERY
# ============================================================

def discover_nta():
    records = []

    soup = fetch_html(NTA_ARCHIVE, "NTA")

    if not soup:
        print("[NTA] Archive unavailable")
        return records

    seen = set()

    # Table rows contain the title and the PDF link.
    for row in soup.find_all("tr"):
        row_text = clean_text(row.get_text(" ", strip=True))

        if not is_actual_question_paper(row_text):
            continue

        for anchor in row.find_all("a", href=True):
            pdf_url = normalise_url(
                urljoin(NTA_ARCHIVE, anchor["href"])
            )

            if not is_pdf_url(pdf_url):
                continue

            record = make_record(
                title=row_text,
                pdf_url=pdf_url,
                source_page=NTA_ARCHIVE,
                source_name="NTA",
                source_type="official",
                context=row_text,
            )

            if record and pdf_url not in seen:
                seen.add(pdf_url)
                records.append(record)

    # Fallback for archive entries not rendered in table rows.
    for anchor in soup.find_all("a", href=True):
        pdf_url = normalise_url(
            urljoin(NTA_ARCHIVE, anchor["href"])
        )

        if not is_pdf_url(pdf_url) or pdf_url in seen:
            continue

        anchor_text = clean_text(
            anchor.get_text(" ", strip=True)
        )

        parent_text = clean_text(
            anchor.parent.get_text(" ", strip=True)
        )

        context = clean_text(
            f"{anchor_text} {parent_text}"
        )

        record = make_record(
            title=context,
            pdf_url=pdf_url,
            source_page=NTA_ARCHIVE,
            source_name="NTA",
            source_type="official",
            context=context,
        )

        if record:
            seen.add(pdf_url)
            records.append(record)

    return records


# ============================================================
# AGLASEM DISCOVERY
# ============================================================

def discover_aglasem():
    records = []
    soup = fetch_html(AGLASEM_ARCHIVE, "AglaSem")

    if not soup:
        print("[AglaSem] Archive unavailable")
        return records

    detail_pages = {}

    for anchor in soup.find_all("a", href=True):
        page_url = normalise_url(
            urljoin(AGLASEM_ARCHIVE, anchor["href"])
        )

        text = clean_text(
            anchor.get_text(" ", strip=True)
        )

        context = clean_text(
            f"{text} {anchor.parent.get_text(' ', strip=True)}"
        )

        year = get_year(context)

        if not year or not START_YEAR <= year <= END_YEAR:
            continue

        if not has_exam_name(context):
            continue

        if not has_question_paper_term(context):
            continue

        if not allowed_url(page_url, "AglaSem"):
            continue

        if is_pdf_url(page_url):
            record = make_record(
                title=context,
                pdf_url=page_url,
                source_page=AGLASEM_ARCHIVE,
                source_name="AglaSem",
                source_type="third_party",
                context=context,
            )

            if record:
                records.append(record)
        else:
            detail_pages[page_url] = context

    for page_url, listing_context in list(
        detail_pages.items()
    )[:MAX_DETAIL_PAGES]:

        page_soup = fetch_html(page_url, "AglaSem")

        if not page_soup:
            continue

        page_title = clean_text(
            page_soup.title.get_text(" ", strip=True)
            if page_soup.title
            else ""
        )

        page_text = clean_text(
            page_soup.get_text(" ", strip=True)
        )

        context = clean_text(
            f"{listing_context} {page_title} {page_text[:3000]}"
        )

        if not is_actual_question_paper(page_title, context):
            continue

        for anchor in page_soup.find_all("a", href=True):
            pdf_url = normalise_url(
                urljoin(page_url, anchor["href"])
            )

            if not is_pdf_url(pdf_url):
                continue

            link_text = clean_text(
                anchor.get_text(" ", strip=True)
            )

            record = make_record(
                title=page_title or listing_context,
                pdf_url=pdf_url,
                source_page=page_url,
                source_name="AglaSem",
                source_type="third_party",
                context=clean_text(
                    f"{context} {link_text}"
                ),
            )

            if record:
                records.append(record)

        time.sleep(REQUEST_DELAY)

    return records


# ============================================================
# EXAMGOAL DISCOVERY
# ============================================================

def discover_examgoal():
    records = []

    soup = fetch_html(EXAMGOAL_ARCHIVE, "ExamGOAL")

    if not soup:
        print("[ExamGOAL] Archive unavailable")
        return records

    detail_pages = {}

    # First collect all year and paper pages.
    for anchor in soup.find_all("a", href=True):
        page_url = normalise_url(
            urljoin(EXAMGOAL_ARCHIVE, anchor["href"])
        )

        anchor_text = clean_text(
            anchor.get_text(" ", strip=True)
        )

        context = clean_text(
            f"{anchor_text} {anchor.parent.get_text(' ', strip=True)}"
        )

        year = get_year(context)

        if not year or not START_YEAR <= year <= END_YEAR:
            continue

        if not has_exam_name(context):
            continue

        if is_excluded(context):
            continue

        if not allowed_url(page_url, "ExamGOAL"):
            continue

        if is_pdf_url(page_url):
            if not has_question_paper_term(context):
                continue

            record = make_record(
                title=context,
                pdf_url=page_url,
                source_page=EXAMGOAL_ARCHIVE,
                source_name="ExamGOAL",
                source_type="third_party",
                context=context,
            )

            if record:
                records.append(record)
        else:
            detail_pages[page_url] = context

    # Inspect individual pages for direct PDF links.
    for page_url, listing_context in list(
        detail_pages.items()
    )[:MAX_DETAIL_PAGES]:

        page_soup = fetch_html(page_url, "ExamGOAL")

        if not page_soup:
            continue

        page_title = clean_text(
            page_soup.title.get_text(" ", strip=True)
            if page_soup.title
            else ""
        )

        page_text = clean_text(
            page_soup.get_text(" ", strip=True)
        )

        context = clean_text(
            f"{listing_context} {page_title} {page_text[:3000]}"
        )

        if not is_actual_question_paper(page_title, context):
            continue

        for anchor in page_soup.find_all("a", href=True):
            pdf_url = normalise_url(
                urljoin(page_url, anchor["href"])
            )

            if not is_pdf_url(pdf_url):
                continue

            link_text = clean_text(
                anchor.get_text(" ", strip=True)
            )

            record = make_record(
                title=page_title or listing_context,
                pdf_url=pdf_url,
                source_page=page_url,
                source_name="ExamGOAL",
                source_type="third_party",
                context=clean_text(
                    f"{context} {link_text}"
                ),
            )

            if record:
                records.append(record)

        time.sleep(REQUEST_DELAY)

    return records


# ============================================================
# MASTER DISCOVERY
# ============================================================

def discover_neet_papers():
    all_records = []

    sources = [
        ("NTA", discover_nta),
        ("AglaSem", discover_aglasem),
        ("ExamGOAL", discover_examgoal),
    ]

    for name, function in sources:
        print(f"\n========== SEARCHING {name} ==========")

        try:
            found = function()
            print(f"[{name}] Verified papers: {len(found)}")
            all_records.extend(found)

        except Exception as exc:
            print(f"[{name} ERROR] {exc}")

    # Deduplicate exact PDF URLs.
    unique = {}

    for record in all_records:
        url = normalise_url(record["source_url"])

        if url not in unique:
            unique[url] = record

        elif record["source_type"] == "official":
            unique[url] = record

    results = list(unique.values())

    # Prefer official records, then latest years.
    results.sort(
        key=lambda item: (
            item["source_type"] != "official",
            -item["year"],
            item["language"],
            item["exam_session"],
        )
    )

    # Print year-wise coverage.
    year_counts = {}

    for record in results:
        year_counts[record["year"]] = (
            year_counts.get(record["year"], 0) + 1
        )

    print("\n========== NEET DISCOVERY SUMMARY ==========")

    print("Total unique PDFs:", len(results))

    print(
        "Official PDFs:",
        sum(r["source_type"] == "official" for r in results),
    )

    print(
        "Third-party PDFs:",
        sum(r["source_type"] == "third_party" for r in results),
    )

    print("\nYear-wise PDF counts:")

    for year in range(START_YEAR, END_YEAR + 1):
        print(f"{year}: {year_counts.get(year, 0)}")

    missing = [
        year
        for year in range(START_YEAR, END_YEAR + 1)
        if year not in year_counts
    ]

    print("\nYears with no discovered PDFs:", missing)

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
            "message": "No verified papers found. Database unchanged.",
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
            r["source_type"] == "official"
            for r in records
        )

        third_party_count = sum(
            r["source_type"] == "third_party"
            for r in records
        )

        year_counts = {}

        for record in records:
            year = record["year"]
            year_counts[year] = year_counts.get(year, 0) + 1

        return {
            "success": True,
            "discovered": len(records),
            "inserted_or_updated": len(records),
            "official_records": official_count,
            "third_party_records": third_party_count,
            "year_wise_counts": year_counts,
            "message": "NEET paper sync completed.",
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
