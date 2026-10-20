#!/usr/bin/env python3
"""Public, key-free job board collector. Python standard library only."""
import datetime as dt, html, json, re, time, sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parent
NOW=dt.datetime.now(dt.timezone.utc)
GEO=re.compile(r'\bbengaluru\b|\bbangalore\b|\bkarnataka\b',re.I)
FIN=re.compile(r'financ|account|audit|tax|payable|receivable|bookkeep|reconcil|billing|invoic|treasury|payroll|fp&a|financial|costing|credit|general ledger|controller|record.to.report|order.to.cash|procure.to.pay|\bmis\b',re.I)
SENIOR=re.compile(r'\bsenior\b|\bstaff\b|\blead\b|\bprincipal\b|\bdirector\b|\bhead\b|\bmanager\b|\bvp\b|\bchief\b',re.I)
ENTRY=re.compile(r'\bfresher\b|\bentry[ -]?level\b|\bgraduate\b|\btrainee\b|\bintern\b|\binternship\b|\bapprentice\b|\bjunior\b|\bassociate\b|\b0\s*(?:-|to|–)\s*[012]\s*(?:years?|yrs?)\b|\bno experience\b',re.I)
YEARS=re.compile(r'\b(\d{1,2})\s*(?:-|to|–)\s*(\d{1,2})\s*(?:years?|yrs?)\b|\b(\d{1,2})\s*\+\s*(?:years?|yrs?)\b|\b(?:minimum|at least)\s*(\d{1,2})\s*(?:years?|yrs?)\b',re.I)
SKILLS=['Excel','Tally','SAP','Power BI','SQL','GST','TDS','Accounts payable','Accounts receivable','Financial reporting','Financial modelling','Budgeting','Forecasting','Reconciliation','Journal entries','Financial statements','Taxation','Auditing','Accounting','IFRS','ERP','MIS','QuickBooks']
DEFAULT={'greenhouse':['stripe','groww','slice','clear','razorpay','meesho','browserstack','freshworks','chargebee','cred','swiggy','phonepe','rippling','plum','apna','urbancompany','zomato','zerodha','instamojo','cashfree','jupiter','smallcase','porter','cultfit','acko','fi','credavenue','yubi','navi','indmoney','upstox','setu','simpl','open','jar','niyo','razorpayx','airwallex','wise','plaid','brex','ramp','deel','remote','stripeindia'], 'lever':['freshworks','postman','canva','atlassian','thoughtspot','browserstack','razorpay','groww','slice','swiggy','cred','meesho','chargebee','cashfree','yubi','smallcase','porter','acko','navi','airwallex','wise','ramp','brex','rippling'], 'ashby':['deel','linear','supabase','n8n','retool','remote','ramp','mercury','brex','airwallex','wise','plaid','clerk','vercel','linearapp','posthog','zapier','notion','openai','anthropic','cursor','pylon','calcom','tella']}
def clean(x):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',str(x or '')))).strip()
def get(url):
 req=Request(url,headers={'User-Agent':'Mozilla/5.0 FinPathJobs/2.0 (public listings)','Accept':'application/json'})
 with urlopen(req,timeout=12) as f:return json.load(f)
def category(t):
 if re.search('intern|trainee|apprentice',t,re.I):return 'Internship / Trainee'
 if re.search('audit|tax',t,re.I):return 'Audit / Tax'
 if re.search('account|payable|receivable|bookkeep|billing|invoice',t,re.I):return 'Accounting / AP-AR'
 if re.search('analyst|fp&a|forecast|mis',t,re.I):return 'Finance Analyst / FP&A'
 return 'Finance Operations'
def norm(title,company,location,desc,url,source,posted,identifier):
 title,company,location,desc=map(clean,(title,company,location,desc))
 if not title or not GEO.search(location) or SENIOR.search(title) or not str(url).startswith('https://'):return None
 if not FIN.search(title):
  # Only allow broadly titled associate/trainee roles when the description is finance-heavy.
  if not ENTRY.search(title) or len(FIN.findall(desc[:3500]))<3:return None
  if re.search(r'engineer|software|product|sales|marketing|customer support|designer',title,re.I):return None
 hits=list(YEARS.finditer(desc[:5500]+' '+title)); minimums=[int(m.group(1) or m.group(3) or m.group(4)) for m in hits]
 if any(n>=3 for n in minimums):return None
 explicit=bool(re.search(r'\bfresher\b|\bentry[ -]?level\b|\bgraduate trainee\b|\bintern(?:ship)?\b|\b0\s*(?:-|to|–)\s*[012]\s*(?:years?|yrs?)\b|\bno experience\b',title+' '+desc[:2500],re.I))
 if not (ENTRY.search(title) or explicit or minimums):return None
 date=str(posted or '')[:10] if re.match(r'\d{4}-\d{2}-\d{2}',str(posted or '')) else ''
 age=None
 if date:
  try:age=(NOW.date()-dt.date.fromisoformat(date)).days
  except ValueError:pass
 # Older listings may remain open; include only if still published on live employer feed.
 if age is not None and age>90:return None
 level='Fresher / Intern' if re.search(r'intern|trainee|apprentice',title,re.I) else ('0–2 years' if minimums or explicit else 'Experience unconfirmed')
 score=65 if explicit else (50 if ENTRY.search(title) else 38)
 if age is not None and 0<=age<=7:score+=18
 elif age is not None and age<=30:score+=8
 skills=[s for s in SKILLS if re.search(r'(?<!\w)'+re.escape(s)+r'(?!\w)',desc,re.I)]
 return dict(id=str(identifier),title=title,company=company,location=location,date=date,type=category(title),level=level,experience=hits[0].group(0) if hits else 'Not specified; verify employer listing',fresher_confirmed=explicit,fit_score=score,url=url,skills=skills,summary=desc[:450],source=source,source_note='Live public employer feed; verify eligibility and closing date')
def boards():
 p=ROOT/'job_sources.json'
 if not p.exists():return DEFAULT
 obj=json.loads(p.read_text(encoding='utf-8'))
 return {k:[v for v in obj.get(k,[]) if isinstance(v,str) and re.fullmatch(r'[\w-]{2,90}',v)] for k in DEFAULT}
def main():
 result=[]; successes=[];errors=[]
 for provider,slugs in boards().items():
  for slug in dict.fromkeys(slugs):
   try:
    if provider=='greenhouse':
     payload=get(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true')['jobs']
     rows=((x.get('title'),slug,(x.get('location') or {}).get('name'),x.get('content'),x.get('absolute_url'),x.get('first_published') or x.get('updated_at'),f'gh:{slug}:{x.get("id")}') for x in payload)
    elif provider=='lever':
     payload=get(f'https://api.lever.co/v0/postings/{slug}?mode=json')
     rows=((x.get('text'),slug,(x.get('categories') or {}).get('location') or ', '.join((x.get('categories') or {}).get('allLocations') or []),x.get('descriptionPlain') or x.get('description'),x.get('hostedUrl') or x.get('applyUrl'),x.get('createdAt'),f'lever:{slug}:{x.get("id")}') for x in payload)
    else:
     payload=get(f'https://api.ashbyhq.com/posting-api/job-board/{slug}')['jobs']
     rows=((x.get('title'),slug,x.get('location'),x.get('descriptionPlain') or x.get('descriptionHtml'),x.get('jobUrl') or x.get('applyUrl'),x.get('publishedAt'),f'ashby:{slug}:{x.get("id") or x.get("jobUrl")}') for x in payload)
    n=0
    for row in rows:
     job=norm(*row[:5],provider.title(),*row[5:])
     if job:result.append(job);n+=1
    successes.append(dict(provider=provider,board=slug,matches=n))
   except (HTTPError,URLError,TimeoutError,ValueError,TypeError,KeyError,OSError) as e:errors.append(f'{provider}/{slug}: {type(e).__name__}: {str(e)[:90]}')
   time.sleep(.07)
 if not successes:
  print('No career sources could be read. Existing jobs.json preserved.',file=sys.stderr);return 1
 unique={}
 for j in result:
  k=(j['company'].lower(),re.sub(r'\W','',j['title'].lower()),j['location'].lower())
  if k not in unique or unique[k]['fit_score']<j['fit_score']:unique[k]=j
 jobs=sorted(unique.values(),key=lambda x:(-x['fit_score'],x['date']))
 feed=dict(updated_at=NOW.isoformat(),source='Public Greenhouse, Lever and Ashby career feeds',total=len(jobs),jobs=jobs,sources_checked=len(successes),sources=successes,source_errors=errors,source_summary=dict(configured=sum(map(len,boards().values())),successful=len(successes),failed=len(errors)))
 (ROOT/'jobs.json').write_text(json.dumps(feed,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print(f'Successful boards: {len(successes)}; failures: {len(errors)}; matching jobs: {len(jobs)}')
 return 0
if __name__=='__main__':sys.exit(main())
