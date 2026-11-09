"""Shared server-journal poll assessment; no health or delivery inference."""
from datetime import datetime
import json

def poll_expectations(raw, controllers):
    """Validate optional operator config. No implicit cadence or observer."""
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError()
            result[key]=value
        return result
    try:
        if raw is None:return {}
        if type(raw) is not str or len(raw)>16384:raise ValueError()
        values=json.loads(raw,object_pairs_hook=pairs)
        if type(values) is not dict or set(values)-set(controllers):raise ValueError()
        for value in values.values():
            if type(value) is not dict or set(value)!={'cadence_seconds','grace_seconds'}:raise ValueError()
            if type(value['cadence_seconds']) is not int or not 1<=value['cadence_seconds']<=86400:raise ValueError()
            if type(value['grace_seconds']) is not int or not 0<=value['grace_seconds']<=3600:raise ValueError()
        return values
    except (ValueError,TypeError,RecursionError):
        raise RuntimeError('invalid Hearth 2 poll expectations') from None


def _time(value):
    if type(value) is not str:raise ValueError()
    stamp=datetime.fromisoformat(value)
    if stamp.tzinfo is None:raise ValueError()
    return stamp


def assess_poll(name, tick, policy, observed_at, epoch):
    state='unknown';reason='no_completed_poll';age=None
    if tick is not None:
        try:
            age=(_time(observed_at)-_time(tick['at'])).total_seconds()
            if age<0:reason='poll_time_in_future';age=None
            elif policy is None:reason='timing_not_configured'
            else:
                state='stale' if age>policy['cadence_seconds']+policy['grace_seconds'] else 'recent'
                reason='poll_overdue' if state=='stale' else 'within_expected_window'
        except (TypeError,ValueError,OverflowError):reason='poll_time_unusable'
    return dict(controller=name,poll_state=state,reason=reason,age_seconds=age,
        last_completed_at=tick['at'] if tick else None,request_id=tick.get('request_id') if tick else None,
        sequence=tick['seq'] if tick else None,restore_epoch=epoch,
        cadence_seconds=policy['cadence_seconds'] if policy else None,
        grace_seconds=policy['grace_seconds'] if policy else None)
