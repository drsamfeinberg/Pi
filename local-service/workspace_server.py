"""Shared, authenticated POC workspace. Bind only loopback; use a private TLS gateway for remote access."""
import argparse
import hashlib
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import threading
import time
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit
import pi_service as ai
import visual_extract

ASSETS = Path(__file__).parent/'workspace'
TEMPLATES = json.loads((ASSETS/'templates.json').read_text())
DB = None
PUBLIC = os.environ.get('PI_PUBLIC_ORIGIN', '').rstrip('/')
SESSIONS = {}
JOBS = {}
CONTROLS = {}
LOCK = threading.RLock()
BUSY = threading.Lock()
FAILURES = {}


def audio_task(audio, suffix, progress, control):
    if suffix not in ['.mp3','.m4a','.wav','.mp4','.webm','.aac','.ogg']: raise ValueError('Unsupported audio format.')
    with tempfile.TemporaryDirectory(prefix='pi-audio-') as folder:
        path=Path(folder)/('recording'+suffix)
        path.write_bytes(audio); path.chmod(0o600)
        if control['cancel'].is_set(): raise ValueError('Transcription canceled. No transcript was saved.')
        process=subprocess.Popen([sys.executable,str(Path(__file__).with_name('audio_worker.py')),str(path),suffix],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,env={**os.environ,'TMPDIR':folder})
        with LOCK:
            control['process']=process
            if control['cancel'].is_set(): process.terminate()
        result=None
        try:
            for line in process.stdout:
                value=json.loads(line)
                if 'stage' in value: progress(value['stage'])
                if 'result' in value: result=value['result']
                if 'error' in value: raise ValueError(value['error'])
            process.wait()
            if control['cancel'].is_set(): raise ValueError('Transcription canceled. No transcript was saved.')
            if process.returncode or result is None: raise ValueError('Transcription process stopped without a result.')
            return result
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
            process.stdout.close()

def db():
    con = sqlite3.connect(DB, timeout=20)
    con.row_factory = sqlite3.Row
    return con


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 200000).hex()


def init_store(directory):
    global DB
    directory.mkdir(parents=True, exist_ok=True); os.chmod(directory, 0o700)
    DB = directory/'cases.sqlite3'
    with db() as con:
        con.executescript('CREATE TABLE IF NOT EXISTS users (name TEXT PRIMARY KEY, salt TEXT, hash TEXT, role TEXT); CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, owner TEXT, version INTEGER, data TEXT); CREATE TABLE IF NOT EXISTS audit (ts REAL, user TEXT, case_id TEXT, action TEXT);')
    os.chmod(DB, 0o600)
    created = {}
    for name, role in [('clinician','clinician'),('worker','worker')]:
        with db() as con:
            if con.execute('SELECT 1 FROM users WHERE name=?',(name,)).fetchone(): continue
        password = secrets.token_urlsafe(14); create_user(name, password, role); created[name] = password
    return created


def create_user(name, password, role='worker'):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{3,30}',name) or not isinstance(password,str) or not 12<=len(password)<=200 or role not in ['worker','clinician']: raise ValueError('Use a 3–30 character username and a password of at least 12 characters.')
    salt = secrets.token_hex(16)
    with db() as con: con.execute('INSERT INTO users VALUES (?,?,?,?)',(name,salt,password_hash(password,salt),role))


def access(user, case):
    return user['role']=='clinician' or case['owner']==user['name']


def get_case(user, case_id):
    with db() as con: row = con.execute('SELECT * FROM cases WHERE id=?',(case_id,)).fetchone()
    if not row or not access(user,row): raise PermissionError('Case unavailable to this account.')
    return json.loads(row['data'])


def save_case(user, case, version, action):
    case['version'] = version+1
    case['updated_at'] = time.time()
    with db() as con:
        result = con.execute('UPDATE cases SET version=?,data=? WHERE id=? AND version=?',(version+1,json.dumps(case),case['id'],version))
        if not result.rowcount: raise ValueError('Another user changed this case. Reload before saving; your edits were not applied.')
        con.execute('INSERT INTO audit VALUES (?,?,?,?)',(time.time(),user['name'],case['id'],action))
    return case


def invalidate(case):
    for report in case['reports'].values():
        report['status']='draft'; report.pop('reviewed_at',None); report.pop('reviewed_by',None)


def match_sources(sources, templates):
    def normalize(value): return re.sub(r'[^a-z0-9]+',' ',value.lower()).strip()
    headings={}
    aliases={'soap_1':['Subjective','Patient-reported symptoms'],'soap_2':['Objective','Examination findings'],'soap_3':['Assessment','Assessment/Comments'],'soap_4':['Plan','Treatment plan']}
    for template in templates:
        for f in template['fields']:
            for label in [f['label']]+aliases.get(f['id'],[]): headings.setdefault(normalize(label),[]).append(f['id'])
    matches={}
    for source in sources:
        for page,text in enumerate(source['pages'],1):
            current=None
            def finish():
                if current and any(line.strip() for line in current['body']):
                    quote='\n'.join(current['body']).strip()
                    citation={'source_id':source['id'],'source_name':source['name'],'page':page,'line':current['line'],'quote':quote}
                    for field in current['ids']: matches.setdefault(field,[]).append({'text':quote,'citations':[citation]})
            for line_number,line in enumerate(text.splitlines(),1):
                prefix,separator,body=line.partition(':'); ids=headings.get(normalize(line.rstrip(':'))) or (headings.get(normalize(prefix)) if separator else None)
                if ids:
                    finish();current={'ids':ids,'line':line_number,'body':[body.strip()] if separator else []}
                elif current:
                    if not line.strip() and current['body']: finish();current=None
                    else: current['body'].append(line)
            finish()
    output={}
    for template in templates:
        fields={}
        for f in template['fields']:
            groups={}
            for item in matches.get(f['id'],[]):
                key=ai.normalized(item['text'])
                if key not in groups: groups[key]=item
                else: groups[key]['citations']+=item['citations']
            candidates=list(groups.values())
            fields[f['id']]={'text':candidates[0]['text'] if len(candidates)==1 else '', 'citations':candidates[0]['citations'] if len(candidates)==1 else [],'candidates':candidates,'conflict':len(candidates)>1,'resolved':False,'edited':False}
        output[template['id']]={'template_id':template['id'],'status':'draft','generation_method':'source_headings','fields':fields}
    return output


def administrative_report(case, template):
    fields={}
    for f in template['fields']:
        text=f.get('static_text',f"Patient/case: {case['case_label']}\nEncounter: {case['encounter']}\nAccident date, attorney and insurance details: complete from verified administrative records.")
        fields[f['id']]={'text':text,'citations':[],'candidates':[],'conflict':False,'resolved':False,'edited':False,'template_text':bool(f.get('static_text'))}
    return {'template_id':template['id'],'status':'draft','administrative':True,'fields':fields}


DEMO_SOURCE_NAME = 'Fictional test evaluation — not a real patient'
DEMO_SENTENCE = 'Not documented in this fictional workflow test; clinician completion required.'

def is_demo_source(source):
    return source.get('demo') is True or source.get('name') == DEMO_SOURCE_NAME

def evidence_sources(case, include_demo=False):
    return [s for s in case['sources'] if s.get('kind') not in ('template', 'example') and s.get('included', True) is not False and (include_demo or not is_demo_source(s))]


def process(case, templates, progress):
    sources = [{k:s[k] for k in ['id','name','pages','kind']} for s in evidence_sources(case)]
    if not sources and any(not t.get('administrative') for t in templates): raise ValueError('Add and include case evidence first. Demo notes and template references are excluded from AI generation.')
    reports = {}
    for i, template in enumerate(templates):
        if template.get('administrative'):
            reports[template['id']]=administrative_report(case,template); continue
        def stage(text): progress(f"Report {i+1}/{len(templates)}: {text}")
        packet = ai.draft({'case_label':case['case_label'],'encounter':case['encounter'],'template':template,'sources':sources},stage)
        report = packet['report']
        report['generation_method'] = 'local_ai'
        report['generated_at'] = time.time()
        report['used_source_ids'] = [s['id'] for s in sources]
        reports[template['id']] = report
    return reports


class Handler(ai.Handler):
    def permitted(self):
        host = self.headers.get('Host',''); origin = self.headers.get('Origin','')
        hosts = [f'127.0.0.1:{self.server.server_port}']
        if PUBLIC: hosts.append(urlsplit(PUBLIC).netloc)
        origins = [f'http://127.0.0.1:{self.server.server_port}'] + ([PUBLIC] if PUBLIC else [])
        return host in hosts and (not origin or origin in origins or bool(re.fullmatch(r'chrome-extension://[a-p]{32}',origin)))

    def do_OPTIONS(self):
        if not self.permitted(): self.send(403,{'error':'Origin not allowed.'}); return
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin',self.headers.get('Origin',''))
        self.send_header('Access-Control-Allow-Headers','Content-Type, X-Pi-Session, X-Pi-CSRF, X-Pi-Audio-Suffix, X-Pi-Token')
        self.send_header('Access-Control-Allow-Methods','GET, POST, OPTIONS'); self.end_headers()

    def user(self, mutate=False):
        if not self.permitted(): raise PermissionError('Origin or host not allowed.')
        cookies=SimpleCookie(self.headers.get('Cookie',''))
        token=self.headers.get('X-Pi-Session','') or (cookies['pi_session'].value if 'pi_session' in cookies else '')
        with LOCK:
            session=SESSIONS.get(token)
            if not session or session['expires']<time.time(): raise PermissionError('Sign in to the workspace.')
        if mutate and not self.headers.get('X-Pi-Session') and not secrets.compare_digest(self.headers.get('X-Pi-CSRF',''),session['csrf']): raise PermissionError('Session verification failed. Sign in again.')
        return session

    def content(self, path):
        routes={'/':'index.html','/app.js':'app.js','/style.css':'style.css','/pdf.mjs':'../pdf.mjs','/pdf.worker.mjs':'../pdf.worker.mjs'}
        name=routes.get(path)
        if not name: self.send(404,{'error':'Not found.'}); return
        file=ASSETS/name
        data=file.read_bytes()
        self.send_response(200); self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript','mjs':'text/javascript','css':'text/css'}[file.suffix[1:]])
        self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        try:
            if not self.permitted(): raise PermissionError('Origin or host not allowed.')
            path=urlsplit(self.path).path
            if not path.startswith('/api/'):
                if path in ['/health'] or path.startswith('/jobs/'): return super().do_GET()
                return self.content(path)
            user=self.user()
            if path=='/api/session': self.send(200,{k:user[k] for k in ['name','role','csrf']}); return
            if path=='/api/templates': self.send(200,TEMPLATES); return
            if path=='/api/cases':
                with db() as con: rows=con.execute('SELECT * FROM cases').fetchall()
                cases=[json.loads(row['data']) for row in rows if access(user,row)]
                self.send(200,[{k:c[k] for k in ['id','case_label','encounter','owner','version']} for c in cases]); return
            if path=='/api/users':
                if user['role']!='clinician': raise PermissionError('Clinician access required.')
                with db() as con: rows=con.execute('SELECT name,role FROM users').fetchall()
                self.send(200,[dict(row) for row in rows]); return
            if path=='/api/health':
                try:
                    with ai.urlopen('http://127.0.0.1:11434/api/tags',timeout=3) as r: names=[m['name'] for m in json.load(r).get('models',[])]
                    model_ready=ai.MODEL in names
                except Exception: model_ready=False; names=[]
                self.send(200,{'model':ai.MODEL,'model_ready':model_ready,'vision_model':visual_extract.MODEL,'vision_ready':visual_extract.MODEL in names}); return
            if path.startswith('/api/jobs/'):
                with LOCK:
                    job=JOBS.get(path.split('/')[-1])
                    if not job or job['user']!=user['name']: raise PermissionError('Job unavailable.')
                    result={k:v for k,v in job.items() if k not in ['user','created']}
                    result['elapsed_seconds']=int(time.time()-job['created'])
                    if job['status'] in ['complete','error']: JOBS.pop(path.split('/')[-1],None)
                self.send(200,result); return
            match=re.fullmatch(r'/api/cases/([a-f0-9]+)(/approved/([a-z0-9_]+)|/audit)?',path)
            if match:
                case=get_case(user,match[1])
                if match[2]=='/audit':
                    with db() as con: rows=con.execute('SELECT ts,user,action FROM audit WHERE case_id=? ORDER BY ts DESC LIMIT 40',(case['id'],)).fetchall()
                    self.send(200,[dict(row) for row in rows]); return
                if match[3]:
                    report=case['reports'].get(match[3])
                    if not report or report['status']!='reviewed_unsigned': raise ValueError('Clinician approval is required before Jane handoff.')
                    self.send(200,{'case_label':case['case_label'],'encounter':case['encounter'],'report':report,'version':case['version']}); return
                self.send(200,case); return
            self.send(404,{'error':'Unknown endpoint.'})
        except PermissionError as e: self.send(403,{'error':str(e)})
        except ValueError as e: self.send(409,{'error':str(e)})
        except Exception: self.send(500,{'error':'Workspace request failed.'})

    def body(self):
        size=int(self.headers.get('Content-Length','0'))
        if not 0<size<=ai.MAX_BODY: raise ValueError('Upload limit: 100 MB.')
        return self.rfile.read(size)

    def launch(self,user,task,control=None):
        if not BUSY.acquire(blocking=False): raise ValueError('A local AI job is running. Wait for it to finish.')
        job_id=secrets.token_hex(16)
        with LOCK:
            for key in list(JOBS):
                if JOBS[key]['status']!='running' and time.time()-JOBS[key]['created']>900: JOBS.pop(key,None)
            JOBS[job_id]={'user':user['name'],'status':'running','stage':'Starting local processing','created':time.time()}
            if control is not None: CONTROLS[job_id]=control
        def run():
            def progress(stage):
                with LOCK: JOBS[job_id]['stage']=stage
            try:
                value=task(progress)
                with LOCK: JOBS[job_id].update(status='complete',result=value)
            except Exception as e:
                error=str(e) if isinstance(e,ValueError) else 'Local processing failed. Check installed models and source format.'
                with LOCK:
                    stage=JOBS[job_id]['stage']
                    JOBS[job_id].update(status='error',error=f'{stage}: {error}')
            finally:
                with LOCK: CONTROLS.pop(job_id,None)
                BUSY.release()
        try:
            self.send(202,{'job_id':job_id}); threading.Thread(target=run,daemon=True).start()
        except Exception: BUSY.release(); raise

    def do_POST(self):
        try:
            if not self.permitted(): raise PermissionError('Origin or host not allowed.')
            path=urlsplit(self.path).path
            if path in ['/generate','/transcribe']: return super().do_POST()
            if path=='/api/login':
                body=json.loads(self.body()); name=body.get('name',''); password=body.get('password','')
                if not isinstance(name,str) or not isinstance(password,str) or len(name)>30 or len(password)>200: raise PermissionError('Invalid credentials.')
                with LOCK:
                    history=FAILURES.setdefault(self.client_address[0],[]); history[:]=[t for t in history if time.time()-t<60]
                    if len(history)>=8: raise PermissionError('Too many attempts. Wait a minute.')
                with db() as con: row=con.execute('SELECT * FROM users WHERE name=?',(name,)).fetchone()
                if not row or not secrets.compare_digest(row['hash'],password_hash(password,row['salt'])):
                    with LOCK: history.append(time.time())
                    raise PermissionError('Invalid credentials.')
                token=secrets.token_urlsafe(32); csrf=secrets.token_urlsafe(24)
                with LOCK: SESSIONS[token]={'name':row['name'],'role':row['role'],'csrf':csrf,'expires':time.time()+28800}
                data=json.dumps({'name':row['name'],'role':row['role'],'csrf':csrf,'session':token}).encode()
                self.send_response(200)
                if self.headers.get('Origin'): self.send_header('Access-Control-Allow-Origin',self.headers['Origin'])
                self.send_header('Set-Cookie',f'pi_session={token}; HttpOnly; SameSite=Strict; Path=/'+('; Secure' if PUBLIC else ''))
                self.send_header('Content-Type','application/json'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data); return
            user=self.user(mutate=True)
            cancel_match=re.fullmatch(r'/api/jobs/([a-f0-9]+)/cancel',path)
            if cancel_match:
                with LOCK:
                    job=JOBS.get(cancel_match[1]); control=CONTROLS.get(cancel_match[1])
                    if not job or job['user']!=user['name']: raise PermissionError('Job unavailable.')
                    if not control: raise ValueError('This job does not support cancellation or has already finished.')
                    control['cancel'].set(); job['stage']='Stopping transcription'
                    child_process=control.get('process')
                    if child_process and child_process.poll() is None: child_process.terminate()
                self.send(200,{'stopping':True}); return
            if path=='/api/logout':
                with LOCK:
                    for token,session in list(SESSIONS.items()):
                        if session is user: SESSIONS.pop(token,None)
                self.send(200,{'ok':True}); return
            if path=='/api/transcribe':
                audio=self.body(); suffix=self.headers.get('X-Pi-Audio-Suffix','')
                control={'cancel':threading.Event()}
                self.launch(user,lambda progress:audio_task(audio,suffix,progress,control),control); return
            body=json.loads(self.body())
            if path=='/api/check-engine':
                self.launch(user,ai.check_report_engine); return
            if path=='/api/visual-extract':
                def read_page(progress):
                    progress('Reading printed text, handwriting, checkboxes and diagram marks locally')
                    ai.WHISPER=None; ai.gc.collect(); ai.unload_ollama()
                    return visual_extract.extract(body)
                self.launch(user,read_page); return
            if path=='/api/users':
                if user['role']!='clinician': raise PermissionError('Clinician access required.')
                create_user(body.get('name',''),body.get('password',''),'worker'); self.send(201,{'ok':True}); return
            if path=='/api/cases':
                name=body.get('case_label',''); encounter=body.get('encounter',''); owner=body.get('owner',user['name'])
                if not isinstance(name,str) or not name.strip() or len(name)>300 or not isinstance(encounter,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',encounter): raise ValueError('Patient label and encounter date are required.')
                if user['role']!='clinician' and owner!=user['name']: raise PermissionError('Workers can create cases only for themselves.')
                with db() as con:
                    if not con.execute('SELECT 1 FROM users WHERE name=?',(owner,)).fetchone(): raise ValueError('Unknown assigned worker.')
                    case={'id':secrets.token_hex(16),'case_label':name,'encounter':encounter,'owner':owner,'version':1,'sources':[],'reports':{},'updated_at':time.time()}
                    con.execute('INSERT INTO cases VALUES (?,?,?,?)',(case['id'],owner,1,json.dumps(case)))
                    con.execute('INSERT INTO audit VALUES (?,?,?,?)',(time.time(),user['name'],case['id'],'created'))
                self.send(201,case); return
            match=re.fullmatch(r'/api/cases/([a-f0-9]+)/(sources|source_selection|details|generate|reports|approve|match)',path)
            if not match: self.send(404,{'error':'Unknown endpoint.'}); return
            case=get_case(user,match[1]); version=body.get('version')
            if version!=case['version']: raise ValueError('Case changed. Reload before applying edits.')
            action=match[2]
            if action=='details':
                name=body.get('case_label',''); encounter=body.get('encounter','')
                if not isinstance(name,str) or not name.strip() or len(name)>300 or not isinstance(encounter,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',encounter): raise ValueError('Patient label and encounter date are required.')
                case['case_label']=name.strip(); case['encounter']=encounter; invalidate(case)
                self.send(200,save_case(user,case,version,'case details edited; approvals cleared')); return
            if action=='source_selection':
                source=next((s for s in case['sources'] if s['id']==body.get('source_id')),None)
                if not source or type(body.get('included')) is not bool: raise ValueError('Invalid source selection.')
                if body['included'] and (source.get('kind') in ('template','example') or is_demo_source(source)): raise ValueError('Demo notes, template references and style examples cannot be used as AI evidence.')
                source['included']=body['included']; invalidate(case)
                self.send(200,save_case(user,case,version,'evidence selection edited; approvals cleared')); return
            if action=='sources':
                source=body.get('source',{}); pages=source.get('pages'); kind=source.get('kind','clinical'); name=source.get('name','')
                if not isinstance(name,str) or not name.strip() or len(name)>300 or kind not in ['clinical','police','imaging','transcript','template','example'] or not isinstance(pages,list) or not pages or len(pages)>500 or any(not isinstance(p,str) for p in pages): raise ValueError('Invalid source.')
                if len(case['sources'])>=20 or sum(len(p) for s in case['sources'] for p in s['pages'])+sum(map(len,pages))>2000000: raise ValueError('Case source limit reached.')
                case['sources'].append({'id':secrets.token_hex(12),'name':name,'pages':pages,'kind':kind,'demo':bool(source.get('demo'))}); invalidate(case)
                self.send(200,save_case(user,case,version,'source added; approvals cleared')); return
            if action=='match':
                ids=body.get('templates',[]); chosen=[t for t in TEMPLATES if t['id'] in ids]
                if not chosen or len(chosen)!=len(set(ids)): raise ValueError('Select supported report templates.')
                case['reports'].update(match_sources(evidence_sources(case,include_demo=True),[t for t in chosen if not t.get('administrative')]))
                for t in chosen:
                    if t.get('administrative'): case['reports'][t['id']]=administrative_report(case,t)
                self.send(200,save_case(user,case,version,'source headings matched (no AI)')); return
            if action=='generate':
                ids=body.get('templates',[]); templates=[t for t in TEMPLATES if t['id'] in ids]
                if not templates or len(templates)!=len(set(ids)): raise ValueError('Select supported report templates.')
                def task(progress):
                    reports=process(case,templates,progress)
                    case['reports'].update(reports)
                    return save_case(user,case,version,'reports generated')
                self.launch(user,task); return
            template=next((t for t in TEMPLATES if t['id']==body.get('template_id')),None)
            if not template: raise ValueError('Unsupported template.')
            report=case['reports'].get(template['id'])
            if action=='reports':
                fields=body.get('fields',{})
                if set(fields)!=set(f['id'] for f in template['fields']) or any(not isinstance(v,str) or len(v)>30000 for v in fields.values()): raise ValueError('Invalid report sections.')
                prior=report or {'fields':{}}
                report={'template_id':template['id'],'status':'draft','administrative':bool(template.get('administrative')),'fields':{f['id']:{'text':fields[f['id']],'citations':prior['fields'].get(f['id'],{}).get('citations',[]),'edited':True,'candidates':[],'conflict':False,'resolved':False} for f in template['fields']}}
                case['reports'][template['id']]=report
                self.send(200,save_case(user,case,version,'draft edited; approval cleared')); return
            if user['role']!='clinician': raise PermissionError('Only the clinician can approve clinical reports.')
            if not body.get('confirmed') or not report or any(not v['text'].strip() for v in report['fields'].values()): raise ValueError('Review and complete all fields or explain why information is not documented.')
            if evidence_sources(case) and any(DEMO_SENTENCE in v['text'] for v in report['fields'].values()): raise ValueError('This report contains the old fictional test text. Generate a new draft from the included case evidence before approval.')
            report.update(status='reviewed_unsigned',reviewed_at=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),reviewed_by=user['name'])
            self.send(200,save_case(user,case,version,'clinician approved unsigned draft'))
        except PermissionError as e: self.send(403,{'error':str(e)})
        except (ValueError,sqlite3.IntegrityError) as e: self.send(409,{'error':str(e) if isinstance(e,ValueError) else 'Username already exists.'})
        except Exception: self.send(500,{'error':'Workspace operation failed.'})


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765); parser.add_argument('--data-dir',type=Path,default=Path(__file__).parent/'private-data'); parser.add_argument('--reset-password')
    args=parser.parse_args(); created=init_store(args.data_dir)
    if args.reset_password:
        password=secrets.token_urlsafe(14); salt=secrets.token_hex(16)
        with db() as con:
            result=con.execute('UPDATE users SET salt=?,hash=? WHERE name=?',(salt,password_hash(password,salt),args.reset_password))
            if not result.rowcount: raise SystemExit('Username does not exist.')
        print(f'New password for {args.reset_password}: {password}',flush=True); return
    print(f'Pi workspace: http://127.0.0.1:{args.port}',flush=True)
    for name,password in created.items(): print(f'Initial login — {name}: {password}',flush=True)
    if not created: print('Use your existing workspace usernames and passwords.',flush=True)
    print('Keep this Terminal window open. Start with fictional records. Local AI requires Ollama and Whisper setup.',flush=True)
    def cleanup():
        while True:
            time.sleep(60)
            with LOCK:
                for key in list(JOBS):
                    if JOBS[key]['status']!='running' and time.time()-JOBS[key]['created']>900: JOBS.pop(key,None)
                for key in list(SESSIONS):
                    if SESSIONS[key]['expires']<time.time(): SESSIONS.pop(key,None)
    threading.Thread(target=cleanup,daemon=True).start()
    ai.ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()

if __name__=='__main__': main()
