# Dubai Job Digest (build in ~30 minutes)

Every Mon-Fri at about 5:30 AM Dubai time, GitHub runs `job_digest.py`, searches Dubai data jobs,
removes senior / old / already-sent / low-salary jobs, and emails you the best ones.
Jobs with no salary shown are still included (marked). Cost: free.

## Setup
1. **Jooble API key** (free): https://jooble.org/api/about -> register -> copy the key.
2. **Gmail App Password**: Google Account -> Security -> turn on 2-Step Verification ->
   https://myaccount.google.com/apppasswords -> create one -> copy the 16 letters.
3. **GitHub**: create a new **private** repository. Upload everything in this folder
   (keep the `.github/workflows/daily-jobs.yml` path exactly).
4. Repo -> Settings -> Secrets and variables -> Actions -> New repository secret. Add 4:
   - `JOOBLE_API_KEY`
   - `GMAIL_USER` (your gmail address)
   - `GMAIL_APP_PASSWORD` (the 16 letters, no spaces)
   - `TO_EMAIL` (where to send; can be the same gmail)
5. Repo -> Actions -> "Daily Dubai job digest" -> Run workflow. Check your email in 1-2 minutes.
6. Done. It now runs by itself Mon-Fri.

## If something fails
- Open Actions -> click the red run -> read the last lines.
- "JOOBLE_API_KEY is missing" -> secret name spelled wrong.
- Email login error -> use the App Password, not your normal password.
- You will also get an email titled "Job digest FAILED" if all searches fail.
- GitHub pauses schedules after ~60 days without activity. Press "Run workflow" once to wake it.

## Change what it looks for
Edit the SETTINGS block at the top of `job_digest.py` (searches, salary, years, skills).

## Bonus portfolio project
`jobs_log.csv` grows every day. After 4 weeks, load it in Power BI:
top skills asked in Dubai, salary ranges, which companies hire most. Put it on your GitHub/portfolio.

## Local test (no internet, no email)
`python job_digest.py --sample` -> creates `digest_preview.html`
