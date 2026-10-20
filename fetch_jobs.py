
#!/usr/bin/env python3
"""FinPath V4: key-free finance job collection, with conservative eligibility checks. Public Greenhouse/Lever/Ashby boards plus Himalayas, Remotive and Jobicy. Not an exhaustive aggregator; never invents jobs or bypasses job-board restrictions. """
import datetime as dt
import html
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
NOW = dt.datetime.now(dt.timezone.utc)
MAX_AGE_DAYS = 90

# These are publicly accessible candidate board IDs; unavailable boards are reported.
BOARDS = {
    'greenhouse': ['stripe', 'groww', 'slice', 'clear', 'porter', 'wise', 'brex', 'remote'],
    'lever': ['freshworks', 'cred', 'meesho', 'porter', 'wise', 'brex', 'airwallex'],
    'ashby': ['deel', 'linear', 'supabase', 'n8n', 'retool', 'remote', 'ramp', 'mercury', 'brex', 'airwallex', 'posthog', 'notion'],
}
LOCAL = re.compile(r'\b(?:bengaluru|bangalore)\b', re.I)
INDIA = re.compile(r'\b(?:india|indian|worldwide|anywhere|global)\b', re.I)
ROLE = [
    (r'\b(?:fp&a|finance|financial|budget(?:ing)?|treasury|working capital)\b', 'Finance Analyst / FP&A'),
    (r'\b(?:accounts?|accounting|accountant|payable|receivable|invoice|invoicing|billing|bookkeep|reconcil|general ledger|record.to.report|procure.to.pay|order.to.cash)\b', 'Accounting / AP-AR'),
    (r'\b(?:audit|auditor|tax|taxation|gst|tds)\b', 'Audit / Tax'),
    (r'\b(?:payroll|credit risk|finance operations)\b', 'Finance Operations'),
]
BAD = re.compile(r'\b(?:video|editor|design|graphic|software|engineer|developer|sales|marketing|recruit|human resources|customer success|customer support|product|fraud|sanctions|verification|kyc|aml|compliance|legal|security|data scientist|machine learning)\b', re.I)
SENIOR = re.compile(r'\b(?:senior|sr\.?|staff|principal|lead|director|manager|head|vice president|vp|chief|architect)\b', re.I)
ENTRY_TITLE = re.compile(r'\b(?:fresher|entry.level|graduate|trainee|apprentice|intern(?:ship)?|junior|new grad|assistant|associate)\b', re.I)
EXPLICIT_FRESH = re.compile(r'\b(?:freshers? welcome|fresh graduates?|entry.level|graduate trainee|0\s*(?:-|–|to)\s*[012]\s*(?:years?|yrs?)|no experience required)\b', re.I)
RANGE = re.compile(r'\b(\d{1,2})\s*(?:-|–|to)\s*(\d{1,2})\s*(?:years?|yrs?)\b', re.I)
PLUS = re.compile(r'\b(\d{1,2})\s*\+\s*(?:years?|yrs?)\b', re.I)
MINIMUM = re.compile(r'\b(?:minimum|at least|min\.?|requires?)\s*(?:of\s*)?(\d{1,2})\s*(?:years?|yrs?)\b', re.I)
SKILLS = ['Excel', 'Power BI', 'Tally', 'SAP', 'GST', 'TDS', 'SQL', 'Python', 'Accounting', 'Reconciliation', 'Financial reporting', 'Forecasting', 'Budgeting', 'Financial modelling', 'Accounts payable', 'Accounts receivable', 'Audit', 'IFRS', 'ERP', 'MIS', 'Payroll', 'QuickBooks', 'Financial statements']

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]; self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('style','script'): self.skip += 1
        elif tag in ('p','li','br','div','h1','h2','h3','h4') and not self.skip:self.parts.append(' ')
    def handle_endtag(self,tag):
        if tag in ('style','script') and self.skip:self.skip-=1
        elif tag in ('p','li','div','h1','h2','h3','h4') and not self.skip:self.parts.append(' ')
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

def plain(x):
    parser=TextExtractor()
    try:parser.feed(str(x or ''))
    except Exception:return re.sub(r'\s+',' ',str(x or '')).strip()
    return re.sub(r'\s+',' ',html.unescape(' '.join(parser.parts))).strip()

def fetch(url):
    req=Request(url,headers={'User-Agent':'FinPathJobs/4.0 public job listing reader','Accept':'application/json'})
    with urlopen(req,timeout=17) as response:return json.load(response)

def date_only(x):
    if isinstance(x,(float,int)):
        try:return dt.datetime.fromtimestamp(x/1000 if x>1e11 else x,dt.timezone.utc).date().isoformat()
        except (ValueError,OverflowError,OSError):return ''
    match=re.match(r'\d{4}-\d{2}-\d{2}',str(x or ''))
    return match.group(0) if match else ''

def years_required(desc):
    # Match candidate experience requirements only; avoid treating company age as years required.
    text=desc[:9000]; values=[]
    for rgx in (RANGE,PLUS,MINIMUM):
        for m in rgx.finditer(text):
            near=text[max(0,m.start()-90):min(len(text),m.end()+50)].lower()
            if re.search(r'\b(?:experience|requirement|qualification|must have|minimum|background|relevant work|professional)\b',near):
                values.append(int(m.group(1)))
    return max(values) if values else None

def role_type(title):
    if BAD.search(title) or SENIOR.search(title):return None
    for pat,label in ROLE:
        if re.search(pat,title,re.I):
            if re.search(r'\b(?:intern|trainee|apprentice)\b',title,re.I):return 'Internship / Trainee'
            return label
    # Do not classify generic associate or intern jobs using company-wide finance text.
    return None

def normalize(title,company,location,description,url,source,posted,identifier,remote=False,eligible_india=False):
    title,company,location,description=map(plain,(title,company,location,description))
    category=role_type(title)
    if not category or not str(url).startswith('https://'):return None
    local=not remote and bool(LOCAL.search(location))
    if not local and not (remote and eligible_india):return None
    req=years_required(description)
    if req is not None and req>2:return None
    explicit=bool(EXPLICIT_FRESH.search(title+' '+description[:3500]))
    junior=bool(ENTRY_TITLE.search(title))
    if not (junior or explicit or req is not None or re.search(r'\b(?:analyst|executive|specialist)\b',title,re.I)):return None
    posted=date_only(posted)
    if posted:
        try:
            age=(NOW.date()-dt.date.fromisoformat(posted)).days
            if age > MAX_AGE_DAYS or age < -2:return None
        except ValueError:posted=''
    else:age=None
    is_best=(req == 0 or (explicit and req in (None,0,1)) or (bool(re.search(r'\b(?:intern|trainee|apprentice)\b',title,re.I)) and req in (None,0,1)))
    level=('Fresher / Intern' if is_best else '0–2 years' if req is not None else 'Experience unconfirmed')
    score=80 if is_best else 60 if req is not None else 42
    if local:score+=10
    if age is not None and age<=7:score+=12
    elif age is not None and age<=30:score+=6
    skills=[s for s in SKILLS if re.search(r'(?<!\w)'+re.escape(s)+r'(?!\w)',description,re.I)]
    # Skip generic company introductions, without pretending to summarise the whole JD.
    excerpt=description[:750]
    return {'id':str(identifier),'title':title,'company':company,'location':location,'date':posted,
      'type':category,'level':level,'experience':f'Minimum {req} years mentioned' if req is not None else 'Not stated; verify with employer',
      'fresher_confirmed':is_best,'fit_score':score,'url':url,'skills':skills,
      'summary':excerpt or 'Check the original listing for responsibilities and qualifications.',
      'source':source,'source_note':'Source listing; verify eligibility and whether vacancy remains open',
      'work_mode':'Bengaluru' if local else 'Remote · India eligible',
      'match_group':'Best matches' if is_best else 'Possible matches'}

def source_result(health,name,matches,error=None):
    record={'source':name,'status':'failed' if error else 'ok','matches':matches}
    if error:record['error']=str(error)[:150]
    health.append(record)

def collect_boards():
    items=[];health=[]
    for provider,slugs in BOARDS.items():
        for slug in slugs:
            name=f'{provider}/{slug}'
            try:
                if provider=='greenhouse':
                    data=fetch(f'https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true')['jobs']
                    rows=((x.get('title'),slug,(x.get('location') or {}).get('name'),x.get('content'),x.get('absolute_url'),x.get('first_published') or x.get('updated_at'),f'gh:{slug}:{x.get("id")}') for x in data)
                elif provider=='lever':
                    data=fetch(f'https://api.lever.co/v0/postings/{slug}?mode=json')
                    rows=((x.get('text'),slug,(x.get('categories') or {}).get('location') or ', '.join((x.get('categories') or {}).get('allLocations') or []),x.get('descriptionPlain') or x.get('description'),x.get('hostedUrl') or x.get('applyUrl'),x.get('createdAt'),f'lever:{slug}:{x.get("id")}') for x in data)
                else:
                    data=fetch(f'https://api.ashbyhq.com/posting-api/job-board/{slug}')['jobs']
                    rows=((x.get('title'),slug,x.get('location'),x.get('descriptionPlain') or x.get('descriptionHtml'),x.get('jobUrl') or x.get('applyUrl'),x.get('publishedAt'),f'ashby:{slug}:{x.get("id") or x.get("jobUrl")}') for x in data)
                found=0
                for row in rows:
                    job=normalize(*row[:5],provider.title(),*row[5:])
                    if job:items.append(job);found+=1
                source_result(health,name,found)
            except Exception as exc:source_result(health,name,0,exc)
            time.sleep(.12)
    return items,health

def collect_himalayas():
    items=[];health=[]
    for term in ('finance','accounting','accounts payable','financial analyst','audit','bookkeeper','tax'):
        for page in (1,2,3):
            name=f'Himalayas/{term}/p{page}'
            try:
                data=fetch('https://himalayas.app/jobs/api/search?'+urlencode({'q':term,'country':'IN','sort':'recent','page':page}))
                found=0
                jobs=data.get('jobs',[])
                for x in jobs:
                    # The country=IN filter includes worldwide-eligible jobs; use provider filtering.
                    regions=x.get('locationRestrictions') or []
                    loc=json.dumps(regions,ensure_ascii=False).lower()
                    if regions and not any(s in loc for s in ('india','"in"','worldwide','anywhere')):continue
                    job=normalize(x.get('title'),x.get('companyName') or 'Employer','Remote · India eligible',x.get('description') or x.get('excerpt'),x.get('applicationLink') or x.get('url'),'Himalayas',x.get('pubDate'),f'him:{x.get("guid")}',True,True)
                    if job:items.append(job);found+=1
                source_result(health,name,found)
                if not jobs:break
            except Exception as exc:source_result(health,name,0,exc);break
            time.sleep(.25)
    return items,health

def collect_remotive():
    items=[];health=[]
    # Global remote feed, filtered by location eligibility locally.
    try:
        data=fetch('https://remotive.com/api/remote-jobs')
        for x in data.get('jobs',[]):
            loc=plain(x.get('candidate_required_location'))
            if not INDIA.search(loc):continue
            job=normalize(x.get('title'),x.get('company_name'),loc,x.get('description'),x.get('url'),'Remotive',x.get('publication_date'),f'remotive:{x.get("id")}',True,True)
            if job:items.append(job)
        source_result(health,'Remotive/global',len(items))
    except Exception as exc:source_result(health,'Remotive/global',0,exc)
    return items,health

def collect_jobicy():
    items=[];health=[]
    # Public Jobicy v2 is last-seven-days only. Its job URL is the provider listing.
    for term in ('finance','accounting','payroll','audit'):
        name='Jobicy/'+term
        try:
            data=fetch('https://jobicy.com/api/v2/remote-jobs?'+urlencode({'count':200,'tag':term}))
            found=0
            for x in data.get('jobs',[]):
                loc=plain(x.get('jobGeo') or x.get('jobLocation') or '')
                if not INDIA.search(loc):continue
                job=normalize(x.get('jobTitle'),x.get('companyName'),loc,x.get('jobDescription'),x.get('url'),'Jobicy',x.get('pubDate'),f'jobicy:{x.get("id")}',True,True)
                if job:items.append(job);found+=1
            source_result(health,name,found)
        except Exception as exc:source_result(health,name,0,exc)
        time.sleep(.2)
    return items,health

def main():
    jobs=[];health=[]
    for collector in (collect_boards,collect_himalayas,collect_remotive,collect_jobicy):
        result,checks=collector();jobs.extend(result);health.extend(checks)
    good=sum(x['status']=='ok' for x in health)
    if good==0:
        print('No feeds responded; preserving prior jobs.json',file=sys.stderr);return 1
    unique={}
    for job in jobs:
        key=(re.sub(r'\W','',job['company'].lower()),re.sub(r'\W','',job['title'].lower()),job['work_mode'])
        if key not in unique or job['fit_score']>unique[key]['fit_score']:unique[key]=job
    jobs=sorted(unique.values(),key=lambda x:(-x['fit_score'],x['date']))
    feed={'updated_at':NOW.isoformat(),'source':'Public employer feeds, Himalayas, Remotive and Jobicy','total':len(jobs),
          'jobs':jobs,'sources_checked':good,'source_summary':{'configured':len(health),'successful':good,'failed':len(health)-good,'with_matches':sum(x.get('matches',0)>0 for x in health)},
          'sources':health,'source_errors':[f"{x['source']}: {x.get('error','')}" for x in health if x['status']=='failed'][:80],
          'disclaimer':'Coverage is partial. Remote eligibility and fresher requirements must be confirmed with the employer.'}
    (ROOT/'jobs.json').write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Sources:',len(health),'responsive:',good,'with matches:',feed['source_summary']['with_matches'],'jobs:',len(jobs))
    print('Bengaluru:',sum(x['work_mode']=='Bengaluru' for x in jobs),'India remote:',sum(x['work_mode']!='Bengaluru' for x in jobs))
    return 0

if __name__=='__main__':sys.exit(main())
