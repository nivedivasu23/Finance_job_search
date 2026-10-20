
#!/usr/bin/env python3
"""FinPath V3: public employer and India-eligible remote job feeds."""
import datetime as dt
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
NOW = dt.datetime.now(dt.timezone.utc)
MAX_AGE_DAYS = 90

BOARDS = {
    "greenhouse": [
        "stripe", "groww", "slice", "clear",
        "porter", "wise", "brex", "remote",
        "ramp", "plaid", "deel", "airwallex"
    ],
    "lever": [
        "freshworks", "cred", "meesho",
        "porter", "wise", "brex", "airwallex"
    ],
    "ashby": [
        "deel", "linear", "supabase", "n8n",
        "retool", "remote", "ramp", "mercury",
        "brex", "airwallex", "posthog", "notion"
    ]
}

LOCAL = re.compile(r"\bbengaluru\b|\bbangalore\b", re.I)

POSITIVE = [
    (
        r"\b(?:finance|financial|fp&a|budget(?:ing)?|treasury|cash management|working capital)\b",
        "Finance Analyst / FP&A"
    ),
    (
        r"\b(?:account(?:s|ing|ant)?|accounts payable|accounts receivable|payable|receivable|billing|invoice|invoicing|bookkeep|general ledger|reconciliation|record.to.report|procure.to.pay|order.to.cash)\b",
        "Accounting / AP-AR"
    ),
    (
        r"\b(?:audit|auditor|tax|taxation|gst|tds)\b",
        "Audit / Tax"
    ),
    (
        r"\b(?:payroll|credit risk|financial reporting|finance operations|finance associate)\b",
        "Finance Operations"
    )
]

EXCLUDE_TITLE = re.compile(
    r"\b(?:video|editor|graphic|design|software|engineer|developer|sales|marketing|recruiter|human resources|hr|customer success|customer support|product|fraud|sanctions|verification|kyc|aml|compliance|legal|security|data scientist|machine learning|research scientist)\b",
    re.I
)

SENIOR = re.compile(
    r"\b(?:senior|sr\.?|staff|principal|lead|director|manager|head|vice president|vp|chief|architect|level [3-9]|iii|iv)\b",
    re.I
)

FRESH = re.compile(
    r"\b(?:fresher|entry.level|graduate|trainee|apprentice|intern(?:ship)?|junior|new grad|early career|0\s*(?:-|–|to)\s*[012]\s*(?:years?|yrs?)|no experience)\b",
    re.I
)

YEARS_RANGE = re.compile(
    r"\b(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s*(?:years?|yrs?)\b",
    re.I
)

YEARS_PLUS = re.compile(
    r"\b(?:at least|minimum|min\.?|over)?\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience)?",
    re.I
)

SKILLS = [
    "Excel", "Power BI", "Tally", "SAP", "GST",
    "TDS", "SQL", "Python", "Accounting",
    "Reconciliation", "Financial reporting",
    "Forecasting", "Budgeting",
    "Financial modelling", "Accounts payable",
    "Accounts receivable", "Audit", "IFRS",
    "ERP", "MIS", "Payroll", "QuickBooks",
    "Financial statements"
]


def plain(x):
    return re.sub(
        r"\s+", " ",
        html.unescape(re.sub(r"<[^>]+>", " ", str(x or "")))
    ).strip()


def fetch(url):
    req = Request(
        url,
        headers={
            "User-Agent": "FinPath/3.0 public-feed-reader",
            "Accept": "application/json"
        }
    )
    with urlopen(req, timeout=16) as response:
        return json.load(response)


def date_only(value):
    if isinstance(value, (int, float)):
        try:
            timestamp = value / 1000 if value > 1e11 else value
            return dt.datetime.fromtimestamp(
                timestamp, dt.timezone.utc
            ).date().isoformat()
        except (ValueError, OSError, OverflowError):
            return ""

    match = re.match(
        r"\d{4}-\d{2}-\d{2}", str(value or "")
    )
    return match.group(0) if match else ""


def min_required(text):
    candidate = text[:5200]
    values = []

    for match in YEARS_RANGE.finditer(candidate):
        context = candidate[
            max(0, match.start() - 70):match.end() + 50
        ].lower()

        if re.search(
            r"experience|require|qualification|background|minimum|year",
            context
        ):
            values.append(int(match.group(1)))

    for match in YEARS_PLUS.finditer(candidate):
        context = candidate[
            max(0, match.start() - 65):match.end() + 40
        ].lower()

        if re.search(
            r"experience|require|qualification|background|minimum",
            context
        ):
            values.append(int(match.group(1)))

    return max(values) if values else None


def classify(title):
    title = plain(title)

    if EXCLUDE_TITLE.search(title) or SENIOR.search(title):
        return None

    for pattern, category in POSITIVE:
        if re.search(pattern, title, re.I):
            if re.search(
                r"\b(?:intern|trainee|apprentice)\b",
                title, re.I
            ):
                return "Internship / Trainee"
            return category

    return None


def normalize(
    title, company, location, description,
    url, source, posted, identifier,
    remote=False, eligible_india=False
):
    title, company, location, description = map(
        plain,
        (title, company, location, description)
    )

    kind = classify(title)

    if not kind or not str(url).startswith("https://"):
        return None

    is_local = bool(LOCAL.search(location)) and not remote

    if not is_local and not (remote and eligible_india):
        return None

    required = min_required(description)

    if required is not None and required > 2:
        return None

    fresh = bool(
        FRESH.search(title + " " + description[:1900])
    )

    if not fresh and required is None:
        if not re.search(
            r"\b(?:associate|analyst|assistant|executive|coordinator|specialist)\b",
            title, re.I
        ):
            return None

    if re.search(
        r"\b(?:intern|trainee|apprentice)\b",
        title, re.I
    ):
        level = "Fresher / Intern"
    elif required is not None:
        level = "0–2 years"
    elif fresh:
        level = "Fresher / Intern"
    else:
        level = "Experience unconfirmed"

    posted = date_only(posted)
    age = None

    if posted:
        try:
            age = (
                NOW.date() -
                dt.date.fromisoformat(posted)
            ).days
        except ValueError:
            pass

    if age is not None:
        if age > MAX_AGE_DAYS or age < -2:
            return None

    if fresh and (required is None or required <= 1):
        score = 76
    elif required is not None:
        score = 65
    else:
        score = 48

    if is_local:
        score += 10

    if age is not None:
        if age <= 7:
            score += 12
        elif age <= 30:
            score += 5

    skills = [
        skill for skill in SKILLS
        if re.search(
            r"(?<!\w)" + re.escape(skill) + r"(?!\w)",
            description, re.I
        )
    ]

    return {
        "id": str(identifier),
        "title": title,
        "company": company,
        "location": location or "India eligible · Remote",
        "date": posted,
        "type": kind,
        "level": level,
        "experience": (
            f"{required}+ years mentioned; verify"
            if required is not None
            else "Not specified; verify employer listing"
        ),
        "fresher_confirmed": fresh and (
            required is None or required <= 2
        ),
        "fit_score": score,
        "url": url,
        "skills": skills,
        "summary": description[:480] or (
            "See original listing for requirements"
        ),
        "source": source,
        "source_note": "Verify details with employer",
        "work_mode": (
            "Bengaluru"
            if is_local else "Remote · India eligible"
        ),
        "match_group": (
            "Best matches"
            if fresh and (
                required is None or required <= 1
            )
            else "Possible matches"
        )
    }


def read_ats():
    items = []
    health = []

    for provider, slugs in BOARDS.items():
        for slug in slugs:
            try:
                if provider == "greenhouse":
                    data = fetch(
                        "https://boards-api.greenhouse.io"
                        f"/v1/boards/{slug}/jobs?content=true"
                    )["jobs"]

                    rows = (
                        (
                            job.get("title"),
                            slug,
                            (job.get("location") or {}).get("name"),
                            job.get("content"),
                            job.get("absolute_url"),
                            job.get("first_published")
                            or job.get("updated_at"),
                            f'gh:{slug}:{job.get("id")}'
                        )
                        for job in data
                    )

                elif provider == "lever":
                    data = fetch(
                        "https://api.lever.co/v0/postings/"
                        f"{slug}?mode=json"
                    )

                    rows = (
                        (
                            job.get("text"),
                            slug,
                            (job.get("categories") or {}).get(
                                "location"
                            ) or ", ".join(
                                (job.get("categories") or {}).get(
                                    "allLocations"
                                ) or []
                            ),
                            job.get("descriptionPlain")
                            or job.get("description"),
                            job.get("hostedUrl")
                            or job.get("applyUrl"),
                            job.get("createdAt"),
                            f'lever:{slug}:{job.get("id")}'
                        )
                        for job in data
                    )

                else:
                    data = fetch(
                        "https://api.ashbyhq.com/posting-api"
                        f"/job-board/{slug}"
                    )["jobs"]

                    rows = (
                        (
                            job.get("title"),
                            slug,
                            job.get("location"),
                            job.get("descriptionPlain")
                            or job.get("descriptionHtml"),
                            job.get("jobUrl")
                            or job.get("applyUrl"),
                            job.get("publishedAt"),
                            f'ashby:{slug}:{job.get("id") or job.get("jobUrl")}'
                        )
                        for job in data
                    )

                count = 0

                for row in rows:
                    item = normalize(
                        *row[:5],
                        provider.title(),
                        *row[5:]
                    )

                    if item:
                        items.append(item)
                        count += 1

                health.append({
                    "source": f"{provider}/{slug}",
                    "status": "ok",
                    "matches": count
                })

            except Exception as exc:
                health.append({
                    "source": f"{provider}/{slug}",
                    "status": "failed",
                    "error": str(exc)[:110]
                })

            time.sleep(0.08)

    return items, health


def read_himalayas():
    items = []
    health = []

    terms = [
        "finance",
        "accounting",
        "accounts payable",
        "financial analyst",
        "audit"
    ]

    for term in terms:
        try:
            url = (
                "https://himalayas.app/jobs/api/search?"
                + urlencode({
                    "q": term,
                    "country": "IN",
                    "sort": "recent",
                    "page": 1
                })
            )

            payload = fetch(url)
            found = 0

            for job in payload.get("jobs", []):
                regions = (
                    job.get("locationRestrictions")
                    or job.get("location")
                    or []
                )

                region_text = json.dumps(
                    regions,
                    ensure_ascii=False
                ).lower()

                if regions and not any(
                    value in region_text
                    for value in [
                        "india", '"in"',
                        '"alpha2": "in"',
                        "worldwide", "anywhere"
                    ]
                ):
                    continue

                item = normalize(
                    job.get("title"),
                    job.get("companyName") or "Employer",
                    "Remote · India eligible",
                    job.get("description")
                    or job.get("excerpt"),
                    job.get("applicationLink")
                    or job.get("url")
                    or job.get("applicationUrl"),
                    "Himalayas",
                    job.get("pubDate")
                    or job.get("publishedAt"),
                    f'himalayas:{job.get("guid") or job.get("id")}',
                    remote=True,
                    eligible_india=True
                )

                if item:
                    items.append(item)
                    found += 1

            health.append({
                "source": "Himalayas/" + term,
                "status": "ok",
                "matches": found
            })

        except Exception as exc:
            health.append({
                "source": "Himalayas/" + term,
                "status": "failed",
                "error": str(exc)[:110]
            })

    return items, health


def main():
    ats, health = read_ats()
    remote, remote_health = read_himalayas()

    health += remote_health

    successful = sum(
        entry["status"] == "ok"
        for entry in health
    )

    if successful == 0:
        print(
            "All sources unavailable. "
            "Preserving existing jobs.json",
            file=sys.stderr
        )
        return 1

    unique = {}

    for job in ats + remote:
        key = (
            re.sub(r"\W", "", job["company"].lower()),
            re.sub(r"\W", "", job["title"].lower()),
            job["work_mode"]
        )

        if (
            key not in unique
            or job["fit_score"] > unique[key]["fit_score"]
        ):
            unique[key] = job

    jobs = sorted(
        unique.values(),
        key=lambda job: (
            -job["fit_score"],
            job["date"]
        )
    )

    feed = {
        "updated_at": NOW.isoformat(),
        "source": (
            "Public employer ATS feeds + "
            "Himalayas remote jobs (with attribution)"
        ),
        "total": len(jobs),
        "jobs": jobs,
        "sources_checked": successful,
        "source_summary": {
            "configured": len(health),
            "successful": successful,
            "failed": len(health) - successful
        },
        "sources": health,
        "source_errors": [
            f"{entry['source']}: {entry.get('error', '')}"
            for entry in health
            if entry["status"] == "failed"
        ][:50],
        "disclaimer": (
            "Public source coverage is partial. "
            "Remote roles must allow India. "
            "Verify each listing before applying."
        )
    }

    output = ROOT / "jobs.json"

    output.write_text(
        json.dumps(feed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

    print(
        f"Feeds working {successful}/{len(health)} | "
        f"Bangalore "
        f"{sum(job['work_mode'] == 'Bengaluru' for job in jobs)} | "
        f"India-eligible remote "
        f"{sum(job['work_mode'] != 'Bengaluru' for job in jobs)} | "
        f"Total {len(jobs)}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
