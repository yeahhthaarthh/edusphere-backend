
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

EXAMGOAL_ARCHIVE = (
    "https://pdf.questions.examgoal.com/"
    "past-years/year-wise/medical/neet"
)

PRACBEE_ARCHIVE = (
    "https://hive.pracbee.com/neet/previous-year-question-papers"
)

AGLASEM_ARCHIVE = (
    "https://docs.aglasem.com/org/nta/neet-ug/question-paper"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
    )
}

TIMEOUT = 25

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# Only explicitly approved hosts are accepted.
# If a source redirects to another host, it is rejected.

ALLOWED_HOSTS = {
    "NTA": {
        "neet.nta.nic.in",
        "nta.ac.in",
        "cdnbbsr.s3waas.gov.in",
    },
    "ExamGOAL": {
        "pdf.questions.examgoal.com",
        "pdf-cdn.examgoal.net",
    },
    "PracBee": {
        "hive.pracbee.com",
        "uploads-pracbee-ramanuj.s3.ap-south-1.amazonaws.com",
    },
    "AglaSem": {
        "aglasem.com",
        "www.aglasem.com",
        "docs.aglasem.com",
        "admission.aglasem.com",
    },
}


# ============================================================
# STRICT DOCUMENT FILTERS
# ============================================================

EXCLUDED_TERMS = [
    "answer key",
    "answer keys",
    "final answer",
    "provisional answer",
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
    "advisory",
    "candidate instructions",
    "instructions to candidates",
    "exam city",
    "examination centre",
    "examination center",
    "exam centre",
    "exam center",
    "city intimation",
    "provisional allotment",
]

PAPER_TERMS = [
    "question paper",
    "question papers",
    "question booklet",
    "question booklets",
    "question book",
    "neet qp",
    "aipmt qp",
    "previous year paper",
    "previous years paper",
    "previous-year paper",
    "past year paper",
    "past years paper",
    "past-year paper",
]


LANGUAGE_RULES = [
    ("English & Hindi", ["english & hindi", "eng & hindi"]),
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
    ("English", ["english"]),
]


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def normalise_url(url):
    url, _ = urldefrag(url)
    return url.strip()


def get_host(url):
    return (urlparse(url).hostname or "").lower()


def allowed_url(url, source):
    parsed = urlparse(url)

    return (
        parsed.scheme == "https"
        and get_host(url) in ALLOWED_HOSTS.get(source, set())
    )


def get_year(text):
    if not text:
        return None

    matches = re.findall(
        r"\b(200[7-9]|201\d|202[0-6])\b",
        text,
        re.I,
    )

    return int(matches[0]) if matches else None


def has_exam_name(text):
    return bool(
        re.search(r"\bNEET\b|\bAIPMT\b", text or "", re.I)
    )


def is_excluded(text):
    text = clean_text(text).lower()

    return any(term in text for term in EXCLUDED_TERMS)


def is_actual_question_paper(title, context=""):
    """
    Conservative validation.

    A document must:
    1. Mention NEET or AIPMT.
    2. Explicitly identify itself as a question paper/booklet.
    3. Not contain excluded administrative/document terms.

    Merely mentioning NEET or AIPMT is never sufficient.
    """

    title_text = clean_text(title).lower()
    context_text = clean_text(context).lower()

    combined = clean_text(
        f"{title_text} {context_text}"
    ).lower()

    if not combined:
        return False

    # Reject administrative and non-paper documents.
    if is_excluded(combined):
        return False

    # Require an explicit exam name.
    if not has_exam_name(combined):
        return False

    # Require explicit question-paper wording.
    if not any(term in combined for term in PAPER_TERMS):
        return False

    return True


def get_language(text):
    text = clean_text(text).lower()

    for language, terms in LANGUAGE_RULES:
        for term in terms:
            if term in text:
                return language

    return "Unknown"


def get_exam_name(year, text):
    text = clean_text(text).lower()

    if "aipmt" in text:
        return "AIPMT"

    if year and year <= 2012:
        return "AIPMT"

    if year in (2014, 2015):
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


def get_anchor_context(anchor, depth=4):
    parts = []
    node = anchor

    for _ in range(depth):
        if node is None:
            break

        parts.append(
            clean_text(node.get_text(" ", strip=True))
        )

        node = node.parent

    return clean_text(" ".join(parts))


def is_pdf_url(url):
    if not url:
        return False

    path = urlparse(url).path.lower()

    return path.endswith(".pdf") or path.endswith(".pdf/")


# ============================================================
# HTTP HELPERS
# ============================================================

def fetch_html(url, source):
    if not allowed_url(url, source):
        print("[BLOCKED SOURCE URL]", url)
        return None

    try:
        response = SESSION.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True,
        )

        if not allowed_url(response.url, source):
            print("[BLOCKED HTML REDIRECT]", response.url)
            return None

        response.raise_for_status()

        content_type = response.headers.get(
            "Content-Type", ""
        ).lower()

        if "html" not in content_type:
            print("[NOT HTML]", url, content_type)
            return None

        return BeautifulSoup(
            response.text,
            "html.parser",
        )

    except requests.RequestException as exc:
        print(f"[HTML ERROR] {url}: {exc}")
        return None


def verify_pdf(url, source):
    """
    Verify that the URL returns a real PDF.
    Redirects are allowed only to approved hosts.
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
            print("[BLOCKED PDF REDIRECT]", response.url)
            response.close()
            return False

        first_bytes = response.raw.read(8)
        response.close()

        return first_bytes.startswith(b"%PDF-")

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
    context="",
):
    title = clean_text(title)
    context = clean_text(context)

    combined = clean_text(
        f"{title} {context}"
    )

    # Strict question-paper validation.
    if not is_actual_question_paper(title, context):
        return None

    year = get_year(combined)

    if not year or not START_YEAR <= year <= END_YEAR:
        return None

    pdf_url = normalise_url(pdf_url)

    if not allowed_url(pdf_url, source_name):
        return None

    if not is_pdf_url(pdf_url):
        return None

    if not verify_pdf(pdf_url, source_name):
        print("[INVALID PDF]", pdf_url)
        return None

    official = source_name == "NTA"
    now = int(time.time())

    return {
        "year": year,
        "exam_date": "",
        "paper_type": "Question Paper",
        "language": get_language(combined),
        "document_type": "Question Paper",
        "title": title,
        "source_url": pdf_url,
        "source_page": source_page,
        "source_authority": "NTA" if official else source_name,
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
        "created_at": now,
        "updated_at": now,
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
# NTA DISCOVERY
# ============================================================

def discover_nta():
    records = []

    soup = fetch_html(NTA_ARCHIVE, "NTA")

    if not soup:
        print("[NTA] Archive unavailable")
        return records

    seen = set()

    # Table-based archive entries.
    for row in soup.find_all("tr"):
        context = clean_text(
            row.get_text(" ", strip=True)
        )

        if not is_actual_question_paper(context):
            continue

        for anchor in row.find_all("a", href=True):
            pdf_url = normalise_url(
                urljoin(NTA_ARCHIVE, anchor["href"])
            )

            if not is_pdf_url(pdf_url):
                continue

            record = make_record(
                title=context,
                pdf_url=pdf_url,
                source_page=NTA_ARCHIVE,
                source_name="NTA",
                context=context,
            )

            if record and pdf_url not in seen:
                seen.add(pdf_url)
                records.append(record)

    # Non-table archive entries.
    for anchor in soup.find_all("a", href=True):
        pdf_url = normalise_url(
            urljoin(NTA_ARCHIVE, anchor["href"])
        )

        if not is_pdf_url(pdf_url) or pdf_url in seen:
            continue

        context = get_anchor_context(anchor)

        if not is_actual_question_paper(context):
            continue

        record = make_record(
            title=context,
            pdf_url=pdf_url,
            source_page=NTA_ARCHIVE,
            source_name="NTA",
            context=context,
        )

        if record and pdf_url not in seen:
            seen.add(pdf_url)
            records.append(record)

    print("[NTA] Verified:", len(records))
    return records


# ============================================================
# EXAMGOAL DISCOVERY
# ============================================================

def discover_examgoal():
    records = []

    soup = fetch_html(
        EXAMGOAL_ARCHIVE,
        "ExamGOAL",
    )

    if not soup:
        print("[ExamGOAL] Archive unavailable")
        return records

    seen = set()

    for anchor in soup.find_all("a", href=True):
        href = normalise_url(
            urljoin(EXAMGOAL_ARCHIVE, anchor["href"])
        )

        if not is_pdf_url(href):
            continue

        context = get_anchor_context(
            anchor,
            depth=5,
        )

        if not is_actual_question_paper(context):
            continue

        year = get_year(context + " " + href)

        if not year or not START_YEAR <= year <= END_YEAR:
            continue

        record = make_record(
            title=context,
            pdf_url=href,
            source_page=EXAMGOAL_ARCHIVE,
            source_name="ExamGOAL",
            context=context,
        )

        if record and href not in seen:
            seen.add(href)
            records.append(record)

    print("[ExamGOAL] Verified:", len(records))
    return records


# ============================================================
# PRACBEE DISCOVERY
# ============================================================

def discover_pracbee():
    records = []

    soup = fetch_html(
        PRACBEE_ARCHIVE,
        "PracBee",
    )

    if not soup:
        print("[PracBee] Archive unavailable")
        return records

    seen = set()

    for anchor in soup.find_all("a", href=True):
        href = normalise_url(
            urljoin(PRACBEE_ARCHIVE, anchor["href"])
        )

        if not is_pdf_url(href):
            continue

        context = get_anchor_context(
            anchor,
            depth=5,
        )

        if not is_actual_question_paper(context):
            continue

        year = get_year(context + " " + href)

        if not year or not START_YEAR <= year <= END_YEAR:
            continue

        record = make_record(
            title=context,
            pdf_url=href,
            source_page=PRACBEE_ARCHIVE,
            source_name="PracBee",
            context=context,
        )

        if record and href not in seen:
            seen.add(href)
            records.append(record)

    print("[PracBee] Verified:", len(records))
    return records


# ============================================================
# AGLASEM DISCOVERY
# ============================================================

def discover_aglasem():
    """
    Only direct PDF links are accepted.
    Document-view pages are not treated as verified PDFs.
    """

    records = []

    soup = fetch_html(
        AGLASEM_ARCHIVE,
        "AglaSem",
    )

    if not soup:
        print("[AglaSem] Archive unavailable")
        return records

    seen = set()

    for anchor in soup.find_all("a", href=True):
        href = normalise_url(
            urljoin(AGLASEM_ARCHIVE, anchor["href"])
        )

        if not is_pdf_url(href):
            continue

        context = get_anchor_context(
            anchor,
            depth=5,
        )

        if not is_actual_question_paper(context):
            continue

        year = get_year(context + " " + href)

        if not year or not START_YEAR <= year <= END_YEAR:
            continue

        record = make_record(
            title=context,
            pdf_url=href,
            source_page=AGLASEM_ARCHIVE,
            source_name="AglaSem",
            context=context,
        )

        if record and href not in seen:
            seen.add(href)
            records.append(record)

    print("[AglaSem] Verified direct PDFs:", len(records))
    return records


# ============================================================
# MASTER DISCOVERY
# ============================================================

def discover_neet_papers():
    all_records = []

    sources = [
        ("NTA", discover_nta),
        ("ExamGOAL", discover_examgoal),
        ("PracBee", discover_pracbee),
        ("AglaSem", discover_aglasem),
    ]

    source_counts = {}

    for name, function in sources:
        print(f"\n========== SEARCHING {name} ==========")

        try:
            found = function()

            source_counts[name] = len(found)
            all_records.extend(found)

        except Exception as exc:
            source_counts[name] = 0
            print(f"[{name} ERROR] {exc}")

    # Deduplicate identical URLs.
    unique = {}

    for record in all_records:
        url = normalise_url(record["source_url"])

        if url not in unique:
            unique[url] = record

        elif record["source_type"] == "official":
            unique[url] = record

    results = list(unique.values())

    results.sort(
        key=lambda item: (
            item["source_type"] != "official",
            -item["year"],
            item["language"],
            item["exam_session"],
        )
    )

    year_counts = {}
    source_year_counts = {}

    for record in results:
        year = record["year"]
        source = record["source_authority"]

        year_counts[year] = (
            year_counts.get(year, 0) + 1
        )

        if source not in source_year_counts:
            source_year_counts[source] = {}

        source_year_counts[source][year] = (
            source_year_counts[source].get(year, 0) + 1
        )

    print("\n========== NEET DISCOVERY SUMMARY ==========")
    print("Total unique PDFs:", len(results))

    print("\nSource counts:")

    for source, count in source_counts.items():
        print(f"{source}: {count}")

    print("\nYear-wise PDF counts:")

    for year in range(START_YEAR, END_YEAR + 1):
        print(
            f"{year}: {year_counts.get(year, 0)}"
        )

    print("\nSource-wise year counts:")

    for source, counts in source_year_counts.items():
        print(f"\n{source}:")

        for year in sorted(counts):
            print(f"  {year}: {counts[year]}")

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
            "message": (
                "No verified papers found. "
                "Database unchanged."
            ),
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

    placeholders = ", ".join(
        ["%s"] * len(columns)
    )

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

        year_counts = {}

        for record in records:
            year = record["year"]

            year_counts[year] = (
                year_counts.get(year, 0) + 1
            )

        return {
            "success": True,
            "discovered": len(records),
            "inserted_or_updated": len(records),
            "year_wise_counts": year_counts,
            "message": "NEET paper sync completed.",
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()
