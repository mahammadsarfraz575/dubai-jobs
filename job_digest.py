"""
Daily Dubai job digest for Mahammad Sarfraz.
Runs on GitHub Actions Mon-Fri, emails a filtered list of NEW jobs.

Test without internet/email:   python job_digest.py --sample
"""
import os, re, sys, csv, json, ssl, time, smtplib, hashlib
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape, unescape
from urllib.parse import quote_plus

# ======================= SETTINGS (edit these) =======================
SEARCHES = [
    "data analyst", "junior data analyst", "power bi analyst",
    "business intelligence analyst", "reporting analyst", "MIS analyst",
    "junior data scientist", "school data analyst", "education data analyst",
    "assessment data analyst", "data analyst SQL Python",
]
LOCATIONS = ["Dubai"]          # add "Abu Dhabi", "Sharjah" if you want
MIN_SALARY_AED = 6000          # monthly. Jobs with NO salary listed are still shown.
MAX_YEARS_REQUIRED = 4         # skip jobs asking for more years than this
MAX_AGE_DAYS = 3               # skip old postings
TOP_N = 30                     # max jobs in one email
SKIP_TITLE_WORDS = ["senior", "sr.", "sr ", "lead", "head of", "manager", "director",
                    "principal", "vp ", "chief", "architect", "intern", "trainee"]
# skills from your CV -> points. More points = better match.
SKILLS = {
    "power bi": 3, "sql": 3, "python": 2, "tableau": 2, "dax": 2, "excel": 1,
    "machine learning": 2, "etl": 1, "dashboard": 1, "reporting": 1, "kpi": 1,
    "statistic": 1, "pandas": 1, "fabric": 2, "azure": 1, "snowflake": 1,
    "school": 3, "education": 3, "student": 2, "academic": 2, "university": 1,
}
TITLE_BONUS = {"data analyst": 5, "bi analyst": 4, "business intelligence": 4,
               "power bi": 4, "reporting analyst": 3, "data scientist": 3, "mis": 2}
JOOBLE_HOST = "https://jooble.org/api"
SEEN_FILE, LOG_FILE = "seen_jobs.json", "jobs_log.csv"
# =====================================================================

AED_PER_USD = 3.67


def clean(text):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def parse_salary(text):
    """Return (monthly_min_aed, monthly_max_aed) or None if not listed/unknown."""
    if not text:
        return None
    t = text.lower().replace(",", "")
    if "hour" in t or "/hr" in t:
        return None
    vals = [float(n) * (1000 if k else 1) for n, k in re.findall(r"(\d+(?:\.\d+)?)\s*(k\b)?", t)]
    vals = [v for v in vals if v >= 500]
    if not vals:
        return None
    if "usd" in t or "$" in t:
        factor = AED_PER_USD
    elif any(x in t for x in ("inr", "₹", "gbp", "£", "eur", "€")):
        return None
    else:
        factor = 1.0
    lo, hi = min(vals) * factor, max(vals) * factor
    annual_words = any(w in t for w in ("year", "annum", "annual", "p.a", "/yr"))
    if annual_words or ("month" not in t and hi > 60000):
        lo, hi = lo / 12, hi / 12
    return lo, hi


def min_years_required(text):
    found = re.findall(r"(\d{1,2})\s*(?:\+|-|–|to)?\s*(?:\d{1,2})?\s*\+?\s*(?:years|year|yrs|yr)\b", (text or "").lower())
    return min(int(x) for x in found) if found else None


def job_key(j):
    raw = j.get("id") or (j["title"] + "|" + j["company"] + "|" + j["link"])
    return hashlib.md5(str(raw).encode()).hexdigest()[:16]


def too_old(updated):
    try:
        d = datetime.fromisoformat(updated[:10]).replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - d > timedelta(days=MAX_AGE_DAYS)
    except Exception:
        return False  # unknown date -> keep


def evaluate(j):
    """Return None if rejected, else enriched dict."""
    title_l = j["title"].lower() + " "
    if any(w in title_l for w in SKIP_TITLE_WORDS):
        return None
    if too_old(j["updated"]):
        return None
    yrs = min_years_required(j["title"] + " " + j["snippet"])
    if yrs is not None and yrs > MAX_YEARS_REQUIRED:
        return None
    sal = parse_salary(j["salary"])
    if sal and sal[1] < MIN_SALARY_AED:
        return None
    text = title_l + j["snippet"].lower()
    hits = [k for k in SKILLS if k in text]
    score = sum(SKILLS[k] for k in hits) + sum(v for k, v in TITLE_BONUS.items() if k in title_l)
    j.update(sal=sal, yrs=yrs, hits=hits, score=score)
    return j


def search_jooble(key, keywords, location):
    import requests
    r = requests.post(f"{JOOBLE_HOST}/{key}", json={"keywords": keywords, "location": location, "page": "1"}, timeout=30)
    r.raise_for_status()
    out = []
    for x in r.json().get("jobs", []):
        out.append(dict(
            id=x.get("id"), title=clean(x.get("title")), company=clean(x.get("company")) or "Not shown",
            location=clean(x.get("location")), salary=clean(x.get("salary")), snippet=clean(x.get("snippet")),
            link=x.get("link", ""), source=clean(x.get("source")), updated=x.get("updated", "") or ""))
    return out


SAMPLE_JOBS = [
    dict(id=1, title="Data Analyst - Education", company="Sample Schools Group", location="Dubai", salary="AED 7,000 - 9,000 per month",
         snippet="Power BI, SQL and Excel dashboards for student assessment data. 2 years experience.", link="https://example.com/1", source="sample", updated=datetime.now().strftime("%Y-%m-%d")),
    dict(id=2, title="Senior Data Analyst", company="BigCo", location="Dubai", salary="", snippet="8+ years", link="https://example.com/2", source="sample", updated=""),
    dict(id=3, title="BI Analyst", company="RetailX", location="Dubai", salary="", snippet="Power BI, SQL, Python. 1-3 years experience.", link="https://example.com/3", source="sample", updated=datetime.now().strftime("%Y-%m-%d")),
    dict(id=4, title="Junior Data Analyst", company="LowPay LLC", location="Dubai", salary="AED 4,500 per month", snippet="Excel reporting", link="https://example.com/4", source="sample", updated=""),
    dict(id=5, title="Data Scientist", company="AI Startup", location="Dubai", salary="AED 120,000 - 150,000 per year", snippet="Python, machine learning, scikit-learn, 3 years", link="https://example.com/5", source="sample", updated=""),
]


def load_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def money(sal):
    if not sal:
        return "Not listed"
    lo, hi = sal
    return f"AED {lo:,.0f}" if abs(hi - lo) < 1 else f"AED {lo:,.0f} - {hi:,.0f} /month"


def build_html(jobs, stats, errors):
    def row(j):
        return (f"<tr><td style='padding:8px;border-bottom:1px solid #ddd'>"
                f"<a href='{escape(j['link'])}' style='font-weight:bold;font-size:15px'>{escape(j['title'])}</a><br>"
                f"{escape(j['company'])} &middot; {escape(j['location'])}<br>"
                f"<b>{money(j['sal'])}</b> &middot; match {j['score']} &middot; via {escape(j['source'] or 'Jooble')}"
                f"{' &middot; ' + str(j['yrs']) + '+ yrs asked' if j['yrs'] else ''}<br>"
                f"<span style='color:#555'>Your CV matches: {escape(', '.join(j['hits']) or 'title only')}</span></td></tr>")
    with_sal = [j for j in jobs if j["sal"]]
    no_sal = [j for j in jobs if not j["sal"]]
    parts = [f"<h2>Dubai jobs for you - {datetime.now().strftime('%a %d %b')}</h2>",
             f"<p>{len(jobs)} new jobs (from {stats['raw']} found, {stats['seen']} already sent before).</p>"]
    if with_sal:
        parts.append(f"<h3>Salary listed, AED {MIN_SALARY_AED:,}+ per month</h3><table width='100%'>" + "".join(map(row, with_sal)) + "</table>")
    if no_sal:
        parts.append("<h3>Salary NOT listed (ask in the interview)</h3><table width='100%'>" + "".join(map(row, no_sal)) + "</table>")
    if not jobs:
        parts.append("<p>No new matching jobs today. Use the quick links below.</p>")
    q = quote_plus("data analyst")
    parts.append("<h3>Check these too (2 min)</h3><ul>"
                 f"<li><a href='https://www.linkedin.com/jobs/search/?keywords={q}&location=Dubai&f_TPR=r86400'>LinkedIn - data analyst, Dubai, last 24h</a></li>"
                 f"<li><a href='https://ae.indeed.com/jobs?q={q}&l=Dubai&fromage=1'>Indeed UAE - last 24h</a></li>"
                 "<li><a href='https://www.bayt.com/en/uae/jobs/data-analyst-jobs/'>Bayt - data analyst jobs UAE</a></li></ul>")
    parts.append("<h3>Your 15 minutes</h3><ol><li><b>6:00-6:03</b> Read the top 5 above. Pick 2-3.</li>"
                 "<li><b>6:03-6:12</b> For each: paste the job description into Claude, get tailored CV bullets + short cover note, apply.</li>"
                 "<li><b>6:12-6:15</b> Write company, date, link in your tracker.</li></ol>")
    if errors:
        parts.append("<p style='color:#b00'>Some searches failed: " + escape("; ".join(errors[:5])) + "</p>")
    return "<html><body style='font-family:Arial,sans-serif'>" + "".join(parts) + "</body></html>"


def send_email(subject, html):
    user, pwd = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"]
    to = os.environ.get("TO_EMAIL") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(user, pwd)
        s.sendmail(user, [to], msg.as_string())


def main():
    sample = "--sample" in sys.argv
    seen = load_json(SEEN_FILE, {})
    cutoff = (datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d")
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    today = datetime.now().strftime("%Y-%m-%d")

    raw, errors, total_searches = [], [], 0
    if sample:
        raw = SAMPLE_JOBS
    else:
        key = os.environ.get("JOOBLE_API_KEY")
        if not key:
            sys.exit("JOOBLE_API_KEY is missing (add it in GitHub > Settings > Secrets).")
        for q in SEARCHES:
            for loc in LOCATIONS:
                total_searches += 1
                try:
                    raw += search_jooble(key, q, loc)
                except Exception as e:
                    errors.append(f"{q}/{loc}: {type(e).__name__}")
                time.sleep(0.5)

    unique = {job_key(j): j for j in raw}
    stats = {"raw": len(unique), "seen": 0}
    fresh = []
    for k, j in unique.items():
        if k in seen:
            stats["seen"] += 1
            continue
        e = evaluate(j)
        if e:
            e["key"] = k
            fresh.append(e)
    fresh.sort(key=lambda j: (j["sal"] is None, -j["score"]))
    fresh = fresh[:TOP_N]

    html = build_html(fresh, stats, errors)
    if sample:
        open("digest_preview.html", "w").write(html)
        print(f"SAMPLE: {len(unique)} raw -> {len(fresh)} kept. Titles:", [j["title"] for j in fresh])
        return

    if total_searches and len(errors) == total_searches:
        send_email("Job digest FAILED - check API key / GitHub Actions log", html)
        sys.exit("All searches failed: " + "; ".join(errors[:3]))

    send_email(f"Dubai jobs: {len(fresh)} new for you ({datetime.now().strftime('%a %d %b')})", html)

    for j in fresh:
        seen[j["key"]] = today
    json.dump(seen, open(SEEN_FILE, "w"))
    new_file = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["date", "title", "company", "location", "salary_text", "salary_min_aed", "salary_max_aed", "years_asked", "score", "skills_matched", "source", "link"])
        for j in fresh:
            lo, hi = j["sal"] or ("", "")
            w.writerow([today, j["title"], j["company"], j["location"], j["salary"], round(lo) if lo != "" else "", round(hi) if hi != "" else "",
                        j["yrs"] or "", j["score"], "|".join(j["hits"]), j["source"], j["link"]])
    print(f"Sent {len(fresh)} jobs.")


if __name__ == "__main__":
    main()
