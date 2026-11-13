"""Concrete Matrix intake: fixed authenticated room/thread, no read-marker writes."""
import hashlib,json,re,sqlite3,ssl,urllib.parse,urllib.request,urllib.error
from pathlib import Path
from offline_relay import Approval,ROOM,THREAD,admit

ORIGIN='https://hearth-matrix.radekal.me'
ACTOR='@codex:hearth.radekal.me'
RAD='@rad:hearth.radekal.me'
CLAUDE='@claude:hearth.radekal.me'

class IntakeUnavailable(RuntimeError):pass


def decode(raw):
    def pairs(items):
        d={}
        for k,v in items:
            if k in d:raise ValueError('duplicate JSON key')
            d[k]=v
        return d
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(ValueError('nonfinite')))


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class MatrixClient:
    def __init__(self,token,*,origin=ORIGIN,fixture=False):
        if type(token) is not str or not token or any(c in token for c in '\r\n'):raise ValueError('matrix credential unavailable')
        if origin!=ORIGIN and not (fixture and re.fullmatch(r'http://127\.0\.0\.1:[0-9]+',origin)):raise ValueError('fixed Matrix origin required')
        self.origin,self._token,self.fixture=origin,token,fixture
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    @classmethod
    def from_env_file(cls,path):
        path=Path(path)
        if path.is_symlink() or not path.is_file() or path.stat().st_size>65536:raise IntakeUnavailable('matrix credential source unavailable')
        selected={};wanted={'MATRIX_HOMESERVER_URL','MATRIX_USER_ID','MATRIX_ACCESS_TOKEN'}
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line:continue
            key,value=line.split('=',1);key=key.strip()
            if key not in wanted:continue
            if key in selected:raise IntakeUnavailable('duplicate Matrix setting')
            value=value.strip()
            if len(value)>=2 and value[0] in "\"'" and value[-1]==value[0]:value=value[1:-1]
            selected[key]=value
        if set(selected)!=wanted or selected['MATRIX_HOMESERVER_URL'].rstrip('/')!=ORIGIN or selected['MATRIX_USER_ID']!=ACTOR:
            raise IntakeUnavailable('Matrix identity binding differs')
        return cls(selected['MATRIX_ACCESS_TOKEN'])
    def request(self,path,query=None,*,method='GET',body=None):
        if not path.startswith('/_matrix/client/v3/') or method not in {'GET','PUT'}:raise ValueError('bounded Matrix route required')
        url=self.origin+path+('?' +urllib.parse.urlencode(query) if query else '')
        data=json.dumps(body,allow_nan=False).encode() if body is not None else None
        if data is not None and len(data)>32768:raise ValueError('bounded post required')
        request=urllib.request.Request(url,data=data,method=method,headers={'Authorization':'Bearer '+self._token,'Content-Type':'application/json','Accept-Encoding':'identity'})
        try:
            with self.opener.open(request,timeout=5) as response:
                if response.geturl()!=url or response.status!=200:raise ValueError()
                raw=response.read(1048577)
                if len(raw)>1048576:raise ValueError()
                result=decode(raw)
                if type(result) is not dict:raise ValueError()
                return result
        except urllib.error.HTTPError as error:
            error.close();raise IntakeUnavailable('Matrix transport unavailable') from None
        except Exception:raise IntakeUnavailable('Matrix transport unavailable') from None
    def whoami(self):
        result=self.request('/_matrix/client/v3/account/whoami')
        if result.get('user_id')!=ACTOR:raise IntakeUnavailable('Matrix principal differs')
        return {'user_id':ACTOR,'authenticated':True}
    def event(self,ident):
        if type(ident) is not str or not ident.startswith('$') or len(ident)>200:raise ValueError('event identity required')
        p='/_matrix/client/v3/rooms/'+urllib.parse.quote(ROOM,safe='')+'/event/'+urllib.parse.quote(ident,safe='')
        value=self.request(p)
        if value.get('event_id')!=ident or value.get('room_id',ROOM)!=ROOM:raise IntakeUnavailable('event origin differs')
        return value
    def page(self,token=None):
        query={'dir':'b','limit':100}
        if token is not None:query['from']=token
        return self.request('/_matrix/client/v3/rooms/'+urllib.parse.quote(ROOM,safe='')+'/messages',query)
    def post(self,room,thread,text):
        if room!=ROOM or thread!=THREAD or type(text) is not str or len(text)>16000:raise ValueError('fixed target required')
        txn='hearth-relay-'+hashlib.sha256(text.encode()).hexdigest()
        body={'msgtype':'m.text','body':text,'m.relates_to':{'rel_type':'m.thread','event_id':THREAD,'is_falling_back':True,'m.in_reply_to':{'event_id':THREAD}}}
        result=self.request('/_matrix/client/v3/rooms/'+urllib.parse.quote(ROOM,safe='')+'/send/m.room.message/'+txn,method='PUT',body=body)
        event=result.get('event_id')
        if type(event) is not str or not event.startswith('$'):raise IntakeUnavailable('post receipt unavailable')
        return event


def content(event):
    c=event.get('content');u=event.get('unsigned',{})
    if (event.get('room_id',ROOM)!=ROOM or event.get('type')!='m.room.message' or type(c) is not dict or type(u) is not dict or u.get('redacted_because')
        or type(c.get('body')) is not str or len(c['body'])>16384):raise ValueError('original message required')
    rel=c.get('m.relates_to',{})
    if type(rel) is not dict or rel.get('rel_type')!='m.thread' or rel.get('event_id')!=THREAD:raise ValueError('source thread differs')
    return c['body']


class MatrixIntake:
    def __init__(self,state,client):
        self.state,self.client=state,client
        with state.tx() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS relay_cursor(id INTEGER PRIMARY KEY,event_id TEXT NOT NULL); CREATE TABLE IF NOT EXISTS relay_intake(work_key TEXT PRIMARY KEY,digest TEXT NOT NULL,approval_event TEXT NOT NULL UNIQUE,work TEXT NOT NULL,review TEXT NOT NULL);')
    def bootstrap(self,ident):
        self.client.whoami();event=self.client.event(ident);content(event)
        with self.state.tx() as db:
            old=db.execute('SELECT event_id FROM relay_cursor WHERE id=1').fetchone()
            if old and old[0]!=ident:raise IntakeUnavailable('preserve existing intake cursor')
            db.execute('INSERT OR IGNORE INTO relay_cursor VALUES(1,?)',(ident,))
    def parse(self,event):
        body=content(event)
        if event.get('sender')!=RAD or not body.startswith('[APPROVED]'):return None
        match=re.search(r'```json\s*(\{.*\})\s*```',body,re.S)
        raw=match.group(1) if match else body[len('[APPROVED]'):].strip()
        packet=decode(raw)
        if type(packet) is not dict or set(packet)!={'hearth_relay_work'}:raise ValueError('typed approval required')
        work=packet['hearth_relay_work'];proof=Approval(ROOM,THREAD,RAD,work['work_id'],work['generation'],work['base_commit'],tuple(work['paths']),event['event_id'],'server_authenticated',tuple(work['aliases']),work['review_event'])
        admit(work,proof)
        review=self.client.event(work['review_event']);review_body=content(review)
        if review.get('sender')!=CLAUDE or not review_body.startswith('[REVIEW]'):raise ValueError('review provenance differs')
        return work,proof,review_body
    def verify(self,work):
        key=work['work_id']+':'+str(work['generation'])
        with self.state.connect() as db:row=db.execute('SELECT * FROM relay_intake WHERE work_key=?',(key,)).fetchone()
        if not row:raise IntakeUnavailable('unregistered work')
        parsed=self.parse(self.client.event(row['approval_event']))
        if not parsed or parsed[0]!=work:raise IntakeUnavailable('approval changed')
        return parsed[1]
    def poll(self):
        with self.state.connect() as db:row=db.execute('SELECT event_id FROM relay_cursor WHERE id=1').fetchone()
        if not row:raise IntakeUnavailable('intake cursor requires recovery')
        prior=row[0];events=[];token=None;found=False
        self.client.whoami()
        for _ in range(3):
            page=self.client.page(token);chunk=page.get('chunk')
            if type(chunk) is not list or len(chunk)>100:raise IntakeUnavailable('invalid bounded Matrix page')
            for event in chunk:
                if type(event) is not dict:raise IntakeUnavailable('invalid source event')
                if event.get('event_id')==prior:found=True;break
                events.append(event)
            if found:break
            token=page.get('end')
            if type(token) is not str or not token or not chunk:break
        if not found:raise IntakeUnavailable('intake cursor gap; no advance')
        staged=[];seen=set()
        for event in reversed(events):
            ident=event.get('event_id')
            if type(ident) is not str or not ident.startswith('$'):raise IntakeUnavailable('missing event identity')
            if ident in seen:continue
            seen.add(ident)
            try:item=self.parse(event)
            except IntakeUnavailable:raise
            except (ValueError,KeyError,TypeError):continue # No room prose grants authority.
            if item:staged.append((event,item))
        with self.state.tx() as db:
            if db.execute('SELECT event_id FROM relay_cursor WHERE id=1').fetchone()[0]!=prior:raise IntakeUnavailable('concurrent cursor changed')
            for event,(work,proof,review) in staged:
                key=work['work_id']+':'+str(work['generation']);raw=json.dumps(work,sort_keys=True,separators=(',',':'));digest=hashlib.sha256(raw.encode()).hexdigest()
                old=db.execute('SELECT digest FROM relay_intake WHERE work_key=?',(key,)).fetchone()
                if old and old[0]!=digest:raise IntakeUnavailable('conflicting review generation; no advance')
                db.execute('INSERT OR IGNORE INTO relay_intake VALUES(?,?,?,?,?)',(key,digest,event['event_id'],raw,review))
            if events:db.execute('UPDATE relay_cursor SET event_id=? WHERE id=1',(events[0]['event_id'],))
        with self.state.connect() as db:
            pending=[]
            for row in db.execute('SELECT * FROM relay_intake ORDER BY rowid'):
                work=decode(row['work']);claimed=db.execute('SELECT 1 FROM jobs WHERE work_id=? AND generation=?',(work['work_id'],work['generation'])).fetchone()
                if not claimed:pending.append(work)
                if len(pending)==100:break
        return pending
