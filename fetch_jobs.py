#!/usr/bin/env python3
"""Bengaluru fresher-first finance vacancies, daily multi-source aggregation.
No invented jobs, no phantom timestamps, and no browser-side API credentials.
"""
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
UTC = dt.timezone.utc
NOW = dt.datetime.now(UTC)
KEYWORDS = [
    'finance fresher', 'accounts fresher', 'accounting trainee',
    'finance internship', 'finance graduate trainee', 'junior accountant',
    'accounts assistant', 'finance associate', 'financial analyst entry level',
    'accounts payable associate', 'accounts receivable associate',
    'audit associate fresher', 'tax associate fresher',
    'reconciliation analyst', 'finance operations analyst', 'fp&a analyst junior',
]
FINANCE = re.compile(r'financ|account|audit|taxation|\btax\b|payable|receivable|bookkeep|reconcil|billing|invoic|treasury|payroll|fp&a|financial|costing|credit analyst', re.I)
NOT_FINANCE = re.compile(r'\bsoftware engineer\b|\bdeveloper\b|\bsales executive\b|\btelecaller\b|\brecruiter\b|\bnurse\b|\bteacher\b|\bfront.?end\b', re.I)
BENGALURU = re.compile(r'bangalore|bengaluru', re.I)
FRESHER = re.compile(r'\bfresher[s]?\b|\bentry.level\b|\bgraduate trainee\b|\bmanagement trainee\b|\bintern(ship)?\b|\bno experience\b|\b0\s*(?:-|to|–)\s*[012]\s*(?:years?|yrs?)\b|\b0\s*(?:years?|yrs?)\b', re.I)
SENIOR = re.compile(r'\bsenior\b|\bmanager\b|\blead\b|\bprincipal\b|\bdirector\b|\bhead of\b', re.I)
YEARS = re.compile(r'\b(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s*(?:years?|yrs?)\b|\b(\d{1,2})\s*\+\s*(?:years?|yrs?)\b', re.I)
SKILLS = ['Excel', 'Tally', 'SAP', 'Power BI', 'SQL', 'GST', 'TDS', 'Accounts payable', 'Accounts receivable', 'Bookkeeping', 'Financial reporting', 'Financial modelling', 'Budgeting', 'Forecasting', 'Reconciliation', 'Journal entries', 'Financial statements', 'Taxation', 'Auditing', 'MS Office', 'Accounting', 'IFRS', 'Communication']


def request_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'FinPath-Job-Aggregator/2.0 (public career listing monitor)', 'Accept':'application/json'})
    with urllib.request.urlopen(req, timeout=23) as response:
        return json.load(response)


def plain(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', str(s or '')))).strip()


def category(title):
    if re.search('intern|trainee|apprentice',title,re.I): return 'Internship / Trainee'
    if re.search('audit|tax',title,re.I): return 'Audit / Tax'
    if re.search('account|payable|receivable|bookkeep|billing',title,re.I): return 'Accounting / AP-AR'
    if re.search('fp&a|plan|forecast|analyst',title,re.I): return 'Finance Analyst / FP&A'
    return 'Finance Operations'


def normalize(title, company, place, desc, url, source, posted, identifier):
    title, company, place, desc = map(plain, (title,company,place,desc))
    if not title or not FINANCE.search(title) or NOT_FINANCE.search(title) or not BENGALURU.search(place): return None
    if not url or not url.startswith('https://'): return None
    yr=YEARS.search(desc[:5500]+' '+title)
    minimum = int(yr.group(1) or yr.group(3)) if yr else None
    maximum = int(yr.group(2)) if yr and yr.group(2) else None
    if minimum is not None and minimum >= 3: return None
    if SENIOR.search(title) and not FRESHER.search(title): return None
    # 'Unspecified' is distinct from confirmed fresher eligibility.
    is_fresher = bool(FRESHER.search(title+' '+desc[:1200])) or minimum == 0
    if minimum == 2: level='1–2 years'
    elif minimum == 1: level='0–2 years'
    elif is_fresher: level='Fresher / Intern'
    else: level='Experience unconfirmed'
    exp = (yr.group(0) if yr else ('Fresher / entry-level mentioned' if is_fresher else 'Not stated — verify before applying'))
    vocab = [s for s in SKILLS if re.search(r'(?<!\w)'+re.escape(s)+r'(?!\w)',desc,re.I)]
    score = (75 if is_fresher else 30) + (10 if category(title)=='Internship / Trainee' else 0) + (4 if minimum == 0 else 0)
    if posted:
        try:
            age=(NOW.date()-dt.date.fromisoformat(posted[:10])).days
            if 0 <= age <= 2: score += 15
            elif 0 <= age <= 7: score += 8
        except ValueError: pass
    return {'id':str(identifier),'company':company or 'Employer not listed','title':title,'location':place,
        'date':posted[:10] if posted else '', 'type':category(title),'level':level,'experience':exp,
        'fresher_confirmed':bool(is_fresher),'fit_score':score,'url':url,'skills':vocab,
        'summary':desc[:420] if desc else 'Open the original listing for role details.',
        'source':source,'source_note':'Employer board' if source=='Greenhouse' else 'Job aggregator — verify on application page'}


results=[]; errors=[]; sources=[]
app_id, app_key = os.getenv('ADZUNA_APP_ID'), os.getenv('ADZUNA_APP_KEY')
if app_id and app_key:
    got=0
    for term in KEYWORDS:
        try:
            params=urllib.parse.urlencode({'app_id':app_id,'app_key':app_key,'results_per_page':50,
                'what':term,'where':'Bangalore','distance':20,'sort_by':'date','max_days_old':21,'content-type':'application/json'})
            data=request_json('https://api.adzuna.com/v1/api/jobs/in/search/1?'+params)
            for row in data.get('results',[]):
                job=normalize(row.get('title'),(row.get('company') or {}).get('display_name'),
                    (row.get('location') or {}).get('display_name'),row.get('description'),
                    row.get('redirect_url'),'Adzuna',row.get('created',''),row.get('id') or row.get('redirect_url'))
                if job: results.append(job);got+=1
        except Exception as e: errors.append(f'Adzuna query {term}: {type(e).__name__}: {e}')
    sources.append({'name':'Adzuna','matched':got})
else: errors.append('Adzuna disabled: configure ADZUNA_APP_ID and ADZUNA_APP_KEY')

# Optional curated company Greenhouse board tokens (comma-separated); no authentication for public GET.
boards=[b.strip() for b in os.getenv('GREENHOUSE_BOARDS','').split(',') if re.fullmatch(r'[a-zA-Z0-9_-]+',b.strip())]
for board in boards:
    try:
        data=request_json(f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true')
        got=0
        for row in data.get('jobs',[]):
            place=(row.get('location') or {}).get('name','')
            job=normalize(row.get('title'),board,place,row.get('content'),row.get('absolute_url'),
                'Greenhouse',row.get('first_published') or '',f'greenhouse:{board}:{row.get("id")}')
            if job: results.append(job);got+=1
        sources.append({'name':f'Greenhouse: {board}','matched':got})
    except Exception as e: errors.append(f'Greenhouse {board}: {type(e).__name__}: {e}')

# Deduplicate across aggregator searches and boards using normalized title + employer.
def unique_key(job):
    norm=lambda s: re.sub(r'[^a-z0-9]+','',s.lower())
    return norm(job['company'])+'|'+norm(job['title'])
unique={}
for job in results:
    key=unique_key(job)
    old=unique.get(key)
    if old is None or (job['source']=='Greenhouse' and old['source']!='Greenhouse') or job['fit_score']>old['fit_score']:
        unique[key]=job
jobs=sorted(unique.values(),key=lambda j:(j['fit_score'],j['date']),reverse=True)
feed={'updated_at':NOW.isoformat(timespec='seconds'),'location':'Bengaluru, Karnataka, India',
      'focus':'Fresher and early-career finance jobs (0–2 years)','source':'Multiple supported sources',
      'sources':sources,'errors':errors,'jobs':jobs}
if not sources or (not jobs and errors):
    raise SystemExit('No reliable successful fresh source data; keeping previous published jobs.json. '+' | '.join(errors[:3]))
(ROOT/'jobs.json').write_text(json.dumps(feed,indent=2,ensure_ascii=False),encoding='utf-8')
print(f'Published {len(jobs)} deduplicated jobs from {len(sources)} source(s). Errors: {len(errors)}')
