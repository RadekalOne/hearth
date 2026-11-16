"""Manual supervised cap evidence. No admin API is configured; never unattended authority."""
from datetime import datetime
import math,re

def check(record,now,*,workspace,seat,supervised=False):
    if supervised is not True:raise ValueError('authoritative_admin_readback_unconfigured')
    if type(record) is not dict:raise ValueError('financial_evidence_missing')
    try:
        observed=datetime.fromisoformat(record['observed_at'])
        age=(now-observed).total_seconds()
        if observed.tzinfo is None or not 0<=age<=900:raise ValueError()
        if record['workspace']!=workspace or record['seat']!=seat or not workspace or not seat:raise ValueError()
        for field in ('override_credits','workspace_credits_spent'):
            value=record[field]
            if type(value) not in (int,float) or not math.isfinite(value) or value!=0:raise ValueError()
        usage=record['usage_percent']
        if type(usage) not in (int,float) or not math.isfinite(usage) or not 0<=usage<100:raise ValueError()
        if record['period']!=now.strftime('%Y-%m'):raise ValueError()
        if not re.fullmatch('[0-9a-f]{64}',record['screenshot_sha256']):raise ValueError()
    except (KeyError,TypeError,ValueError,OverflowError):raise ValueError('financial_evidence_refused') from None
    return {k:record[k] for k in ('observed_at','period','usage_percent','screenshot_sha256')}

def read_manual(record_path,screenshot_path):
    """Trusted operator transcribes console screenshot; no OCR/admin API claim."""
    import hashlib,json
    from pathlib import Path
    p,s=Path(record_path),Path(screenshot_path)
    if p.is_symlink() or s.is_symlink() or p.stat().st_size>16384 or s.stat().st_size>20_000_000:raise ValueError('bounded_private_evidence_required')
    record=json.loads(p.read_text(encoding='utf-8'))
    if record.get('screenshot_sha256')!=hashlib.sha256(s.read_bytes()).hexdigest():raise ValueError('screenshot_hash_mismatch')
    return record
