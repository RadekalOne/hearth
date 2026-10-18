"""Reason-before-result records. The service supplies trusted authorship.

Prediction timestamps establish recording order, not private knowledge of results.
"""
import json
from datetime import date

SCHEMA='commons.journal.v1'
def identity(author):return author.removeprefix('@').split(':',1)[0]
PREDICTION_FIELDS={'title':160,'decision':4000,'reasoning':4000,'prediction':4000,'falsifier':3000,'confidence':6,'check_date':10,'tradeoffs':3000}
OUTCOME_FIELDS={'observed_result':4000,'comparison':3000,'verdict':12,'cause_unknown':None,'cause':3000}
CORRECTION_FIELDS={'status':10,'explanation':3000}

def validate(data,record_type):
    fields=PREDICTION_FIELDS if record_type=='prediction' else CORRECTION_FIELDS if record_type=='correction' else OUTCOME_FIELDS
    if set(data)!=set(fields):raise ValueError('Supply exactly the journal fields')
    for name,maximum in fields.items():
        if name=='cause_unknown':
            if type(data[name]) is not bool:raise ValueError('cause_unknown must be boolean')
        elif not isinstance(data[name],str) or len(data[name])>maximum or (name not in {'tradeoffs','cause'} and not data[name].strip()):
            raise ValueError(f'{name} must be bounded text')
    if record_type=='prediction':
        if data['confidence'] not in {'low','medium','high'}:raise ValueError('Invalid confidence')
        try:parsed=date.fromisoformat(data['check_date'])
        except ValueError:raise ValueError('check_date must be an ISO date') from None
        if parsed.isoformat()!=data['check_date']:raise ValueError('check_date must be YYYY-MM-DD')
    elif record_type=='correction':
        if data['status'] not in {'wrong','superseded'}:raise ValueError('Invalid self-correction status')
    else:
        if data['verdict'] not in {'supported','falsified','inconclusive'}:raise ValueError('Invalid verdict')
        if data['cause_unknown'] and data['cause']!='':raise ValueError('Unknown cause must not include a claimed cause')
        if not data['cause_unknown'] and not data['cause'].strip():raise ValueError('Provide the evidenced cause or mark it unknown')
    return data

class Journal:
    def __init__(self,store):self.store=store
    def predict(self,*,author,source_refs,request_id,**fields):
        validate(fields,'prediction')
        return self.store.create(author=author,collection='journal',kind='prediction',content=json.dumps({'schema':SCHEMA,'record_type':'prediction',**fields},ensure_ascii=False,sort_keys=True),source_refs=source_refs,links=[],request_id=request_id)
    def outcome(self,*,author,entry_id,source_refs,request_id,**fields):
        parent=self.read(entry_id)
        if parent['data']['record_type']!='prediction':raise ValueError('Outcome target must be a prediction')
        if identity(author)==identity(parent['author']):raise ValueError('A different authenticated participant must record the outcome')
        validate(fields,'outcome')
        return self.store.create(author=author,collection='journal',kind='outcome',content=json.dumps({'schema':SCHEMA,'record_type':'outcome',**fields},ensure_ascii=False,sort_keys=True),source_refs=source_refs,links=[entry_id],request_id=request_id)
    def correct(self,*,author,entry_id,source_refs,request_id,**fields):
        parent=self.read(entry_id,True)
        if identity(author)!=identity(parent['author']):raise ValueError('Only the original author may self-correct')
        validate(fields,'correction')
        return self.store.create(author=author,collection='journal',kind='correction',content=json.dumps({'schema':SCHEMA,'record_type':'correction',**fields},ensure_ascii=False,sort_keys=True),source_refs=source_refs,links=[entry_id],request_id=request_id)
    def read(self,entry_id,_parent=False):
        entry=self.store.read(entry_id)
        if entry['collection']!='journal':raise ValueError('Not a journal record')
        parts=[entry['content']];offset=entry['next_offset']
        while offset is not None:
            if len(parts)>17:raise ValueError('Invalid journal pagination')
            page=self.store.read(entry_id,offset);parts.append(page['content']);offset=page['next_offset']
        try:data=json.loads(''.join(parts))
        except (ValueError,TypeError):raise ValueError('Not a structured journal record') from None
        if not isinstance(data,dict) or data.get('schema')!=SCHEMA or not isinstance(data.get('record_type'),str) or data['record_type'] not in {'prediction','outcome','correction'}:raise ValueError('Invalid journal schema')
        kind=data['record_type']
        if kind!=entry['kind'] or (_parent and kind!='prediction'):raise ValueError('Invalid journal parent or kind')
        validate({k:v for k,v in data.items() if k not in {'schema','record_type'}},kind)
        if kind=='prediction':
            if entry['links']:raise ValueError('Predictions cannot rewrite earlier records')
        else:
            if len(entry['links'])!=1:raise ValueError('Outcome must link one prediction')
            parent=self.read(entry['links'][0],True)
            same=identity(entry['author'])==identity(parent['author'])
            if same!=(kind=='correction') or entry['created_at']<parent['created_at']:raise ValueError('Invalid linked author or recording order')
        return {**{key:entry[key] for key in ('entry_id','collection','kind','author','created_at','source_refs','links')},'sha256':entry['payload_sha256'],'data':data}
    def list(self,cursor=''):
        page=self.store.list('journal',cursor);entries=[];skipped=0
        for item in page['entries']:
            try:record=self.read(item['entry_id'])
            except ValueError:skipped+=1;continue
            data=record['data']
            entries.append({**item,'record_type':data['record_type'],'title':data.get('title') or ('Self-correction: '+data['status'] if data['record_type']=='correction' else 'Later outcome: '+data['verdict'])})
        return {'entries':entries,'next_cursor':page['next_cursor'],'unstructured_entries':skipped}
