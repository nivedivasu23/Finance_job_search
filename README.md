# FinPath — Bengaluru fresher finance opportunities

A shareable website for nontechnical visitors: automatically displays collected openings and visualizes role skills. **No user search on third-party sites is required.** One-time site-owner deployment and a supported jobs API are required for automatic updates.

## Collection coverage

- Search 16 overlapping terms: finance fresher, accounting trainee, finance internship, graduate trainee, junior accountant, accounts assistant, financial analyst entry-level, accounts payable/receivable, audit and tax associate, finance operations, FP&A junior, and related terms.
- Source 1: **Adzuna India jobs API** using app ID and key (required for broad market coverage). Job API visibility is not equivalent to exhaustive access to LinkedIn, Naukri, Internshala, Indeed, or every employer.
- Source 2: **Greenhouse public employer job-board endpoints**, for a configurable list of company board tokens. Optional; no auth needed for public job GET. Add only actual verified tokens. Public boards are employer-specific, not a universal market feed.
- Each daily run deduplicates roles, rejects 3+ years when explicitly required and most senior-titled roles, prioritizes documented fresher or internship requirements, extracts mentioned skills, and clearly labels jobs whose experience requirements were not stated.
- A third-party aggregator’s redirected application link may go to a job-board posting rather than a direct employer form. Verify each job is still open before applying.
- Sources can fail or omit postings; **"everywhere" cannot be guaranteed** without additional licensed feeds/individual provider agreements.

## One-time site-owner deployment

1. Create a GitHub repository and upload these files, including `.github/workflows/daily.yml`.
2. Obtain Adzuna API credentials via https://developer.adzuna.com/; confirm India coverage and API terms.
3. Repo → Settings → Secrets and variables → Actions: set `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`.
4. Optional: Repo → Settings → Secrets and variables → Actions → Variables: `GREENHOUSE_BOARDS` = comma-separated verified employer tokens, e.g. `companyA,companyB` (not literal placeholders).
5. Settings → Actions → General → Workflow permissions: allow read/write to commit the job feed.
6. Actions → *Refresh Bengaluru fresher finance jobs* → Run workflow. Confirm `jobs.json` is populated.
7. Settings → Pages → Deploy from branch `main`, root. Share the resulting public link.

Daily GitHub Actions schedule is **08:00 IST** (GitHub scheduled execution can be delayed); HTML loads published `jobs.json` when opened and checks for changes hourly. The dashboard is *not live until deployed*. A locally opened HTML file shows an empty list if there is no locally adjacent `jobs.json`, rather than representing sample jobs as fresh vacancies.

No secrets are stored client-side. Saved jobs persist only in each visitor’s browser.
