#!/usr/bin/env python3
"""Key-free collector for public employer job boards. Standard library only."""
import datetime as dt
import html
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent
NOW = dt.datetime.now(dt.timezone.utc)
BOARDS_FILE = ROOT / 'job_sources.json'
OUT = ROOT / 'jobs.json'

# Example company board identifiers. Only successful public feeds are used;
# an identifier being present does NOT establish that company is hiring.
DEFAULT_BOARDS = {
    'greenhouse': ['razorpay', 'meesho', 'browserstack', 'freshworks', 'chargebee', 'cred', 'groww', 'swiggy', 'phonepe', 'stripe', 'rippling', 'plum', 'slice', 'apna', 'clear', 'urbancompany'],
    'lever': ['postman', 'atlassian', 'canva', 'thoughtspot', 'browserstack', 'freshworks', 'razorpay'],
    'ashby': ['linear', 'deel', 'supabase', 'remote', 'n8n', 'retool']
}
GEO = re.compile(r'\bbengaluru\b|\bbangalore\b', re.I)
FIN = re.compile(r'financ|account|audit|taxation|\btax\b|payable|receivable|bookkeep|reconcil|billing|invoic|treasury|payroll|fp&a|financial|costing|credit|general ledger|bookkeeping',re.I)
SENIOR = re.compile(r'\bsenior\b|\bstaff\b|\blead\b|\bprincipal\b|\bdirector\b|\bhead of\b|\bmanager\b|\bvp\b|\bchief\b',re.I)
ENTRY = re.compile(r'\bfresher\b|\bentry[ -]?level\b|\bgraduate\b|\btrainee\b|\bintern(?:ship)?\b|\bapprentice\b|\bjunior\b|\bassociate\b|\b0\s*(?:-|to|–)\s*[012]\s*(?:years?|yrs?)\b|\bno experience\b',re.I)
YEARS = re.compile(r'\b(\d{1,2})\s*(?:-|to|–)\s*(\d{1,2})\s*(?:years?|yrs?)\b|\b(\d{1,2})\s*\+\s*(?:years?|yrs?)\b|\b(?:minimum|at least)\s*(\d{1,2})\s*(?:years?|yrs?)\b',re.I)
SKILLS = ['Excel','Tally','SAP','Power BI','SQL','GST','TDS','Accounts payable','Accounts receivable','Bookkeeping','Financial reporting','Financial modelling','Budgeting','Forecasting','Reconciliation','Journal entries','Financial statements','Taxation','Auditing','MS Office','Accounting','IFRS','Communication']

def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]*>', ' ', str(value or '')))).strip()

def request_json(url):
    req = Request(url, headers={'User-Agent':'FinPath-Fresher-Finance-Collector/1.0', 'Accept':'application/json'})
    with urlopen(req,timeout=18) as res:
        return json.load(res)

def cat(title):
    if re.search(r'intern|trainee|apprentice',title,re.I): return 'Internship / Trainee'
    if re.search(r'audit|tax',title,re.I): return 'Audit / Tax'
    if re.search(r'account|payable|receivable|bookkeep|billing',title,re.I): return 'Accounting / AP-AR'
    if re.search(r'fp&a|analyst|forecast',title,re.I): return 'Finance Analyst / FP&A'
    return 'Finance Operations'

def iso_date(value):
    if value is None: return ''
    if isinstance(value,(int,float)):
        try: return dt.datetime.fromtimestamp(value/1000 if value>10**11 else value,dt.timezone.utc).date().isoformat()
        except (ValueError,OverflowError,OSError): return ''
    found=re.match(r'\d{4}-\d{2}-\d{2}',str(value))
    return found.group(0) if found else ''

def normalize(title,company,location,description,url,source,posted,identifier):
    title,company,location,description=map(clean,(title,company,location,description))
    if not title or not FIN.search(title) or SENIOR.search(title) or not GEO.search(location): return None
    if not str(url or '').startswith('https://'): return None
    hits=list(YEARS.finditer(description[:6000]+' '+title))
    minimums=[int(m.group(1) or m.group(3) or m.group(4)) for m in hits]
    if minimums and max(minimums)>=3: return None
    explicit=bool(re.search(r'\bfresher\b|\bentry[ -]?level\b|\bgraduate trainee\b|\bintern(?:ship)?\b|\b0\s*(?:-|to|–)\s*[012]\s*(?:years?|yrs?)\b|\bno experience\b',title+' '+description[:2500],re.I))
    beginner=bool(ENTRY.search(title)) or explicit
    if not beginner and not minimums: return None  # avoid filling fresher view with unknown mid-level roles
    if minimums and min(minimums)>2: return None
    level='Fresher / Intern' if re.search(r'intern|trainee|apprentice',title,re.I) else ('0–2 years' if minimums or explicit else 'Experience unconfirmed')
    exp=hits[0].group(0) if hits else ('Fresher / entry-level wording' if explicit else 'Not stated; check original listing')
    skills=[s for s in SKILLS if re.search(r'(?<!\w)'+re.escape(s)+r'(?!\w)',description,re.I)]
    date=iso_date(posted)
    score=65 if explicit else 40
    if minimums and min(minimums)==0: score+=8
    if date:
        try:
            age=(NOW.date()-dt.date.fromisoformat(date)).days
            if 0<=age<=3:score+=15
            elif 0<=age<=14:score+=7
        except ValueError:pass
    return {'id':str(identifier),'title':title,'company':company,'location':location,'date':date,
            'type':cat(title),'level':level,'experience':exp,'fresher_confirmed':explicit,
            'fit_score':score,'url':url,'skills':skills,'summary':description[:420] or 'Check the original job description.',
            'source':source,'source_note':'Public employer careers feed; verify eligibility before applying'}

def load_sources():
    if not BOARDS_FILE.exists(): return DEFAULT_BOARDS
    config=json.loads(BOARDS_FILE.read_text(encoding='utf-8'))
    return {k:[x for x in config.get(k,[]) if isinstance(x,str) and re.fullmatch(r'[a-zA-Z0-9_-]{2,90}',x)] for k in ('greenhouse','lever','ashby')}

def collect():
    boards=load_sources()
    jobs=[];sources=[];errors=[];success=0
    for provider,slugs in boards.items():
        for slug in dict.fromkeys(slugs):
            try:
                if provider=='greenhouse':
                    payload=request_json(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true')
                    data=payload.get('jobs',[])
                    parsed=((x.get('title'),slug,(x.get('location') or {}).get('name'),x.get('content'),x.get('absolute_url'),x.get('first_published') or x.get('updated_at'),f'gh:{slug}:{x.get("id")}') for x in data)
                elif provider=='lever':
                    data=request_json(f'https://api.lever.co/v0/postings/{slug}?mode=json')
                    parsed=((x.get('text'),slug,(x.get('categories') or {}).get('location') or (x.get('categories') or {}).get('allLocations'),x.get('descriptionPlain') or x.get('description'),x.get('hostedUrl') or x.get('applyUrl'),x.get('createdAt'),f'lever:{slug}:{x.get("id")}') for x in data)
                else:
                    payload=request_json(f'https://api.ashbyhq.com/posting-api/job-board/{slug}')
                    data=payload.get('jobs',[])
                    parsed=((x.get('title'),slug,x.get('location'),x.get('descriptionPlain') or x.get('descriptionHtml'),x.get('jobUrl') or x.get('applyUrl'),x.get('publishedAt'),f'ashby:{slug}:{x.get("id") or x.get("jobUrl")}') for x in data)
                count=0
                for record in parsed:
                    item=normalize(*record[:5],provider.title(),*record[5:])
                    if item:jobs.append(item);count+=1
                success+=1
                sources.append({'provider':provider,'board':slug,'matches':count})
            except (HTTPError,URLError,TimeoutError,ValueError,TypeError,KeyError,OSError) as e:
                errors.append(f'{provider}/{slug}: {type(e).__name__}: {str(e)[:120]}')
            time.sleep(.15)
    unique={}
    for j in jobs:
        key=(re.sub(r'\W+','',j['company'].lower()),re.sub(r'\W+','',j['title'].lower()),j['location'].lower())
        if key not in unique or j['fit_score']>unique[key]['fit_score']:unique[key]=j
    result=sorted(unique.values(),key=lambda j:(-j['fit_score'],j['date']),reverse=False)
    return result,sources,errors,success

def main():
    jobs,sources,errors,success=collect()
    print(f'Career boards read: {success}; fresher finance matches: {len(jobs)}')
    for error in errors[:15]:print('Source warning:',error)
    if success==0:
        print('No employer feeds could be read; keeping previously published jobs.json.',file=sys.stderr)
        return 1
    # Successful fetch, even if zero matches: publish an honest empty feed.
    feed={'updated_at':NOW.isoformat(),'source':'Greenhouse, Lever and Ashby employer career feeds',
          'total':len(jobs),'jobs':jobs,'sources_checked':success,'sources':sources,'source_errors':errors[:40]}
    OUT.write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Published {len(jobs)} jobs to {OUT}')
    return 0

if __name__=='__main__':sys.exit(main())
