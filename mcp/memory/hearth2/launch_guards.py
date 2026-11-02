"""Account gates over trusted controller observations, never worker assertions.

No provider call, account setting change or credential read occurs here. A live
collector must supply fresh native observations and independently check the
environment/files/config route before each launch. These functions do not turn
an old UI review into a live allowance measurement or a hard harm/spend bound.
"""
from datetime import datetime
import math
from .store import RecordError, timestamp


def _fresh(observed_at, now):
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise RecordError('trusted launch clock required')
    observed = timestamp(observed_at)
    age = (now-observed).total_seconds()
    if not 0 <= age <= 60:
        raise RecordError('fresh native account observation required')
    return observed.isoformat()


def _route(route, provider):
    if (not isinstance(route, dict) or route.get('configured_provider') != provider
            or route.get('native_login_present') is not True
            or any(route.get(key) is not False for key in
                   ['api_key_present', 'unexpected_environment', 'other_credentials_present'])):
        raise RecordError('native subscription credential route unavailable')


def _number(value):
    # Integers are finite; converting an untrusted large integer to float can
    # overflow before the range check has a chance to refuse it.
    return type(value) is int or type(value) is float and math.isfinite(value)


def codex_launch_check(*, account, limits, route, observed_at, now):
    observed = _fresh(observed_at, now)
    _route(route, 'openai')
    if (not isinstance(account, dict) or account.get('requiresOpenaiAuth') is not True
            or not isinstance(account.get('account'), dict)
            or account['account'].get('type') != 'chatgpt'):
        raise RecordError('native ChatGPT account required')
    rates = limits.get('rateLimits') if isinstance(limits, dict) else None
    credits = rates.get('credits') if isinstance(rates, dict) else None
    if (not isinstance(credits, dict) or credits.get('hasCredits') is not False
            or credits.get('unlimited') is not False):
        raise RecordError('purchased or unknown credit fallback refused')
    usage = {}
    for key in ['primary', 'secondary']:
        if key not in rates:
            raise RecordError('native limit window shape changed')
        window = rates[key]
        if window is None:
            continue
        used = window.get('usedPercent') if isinstance(window, dict) else None
        if not _number(used) or not 0 <= used < 100:
            raise RecordError('native included allowance unavailable')
        usage[key] = used
    if not usage:
        raise RecordError('native included allowance unknown')
    return {'provider':'openai', 'account_type':'chatgpt', 'used_percent':usage,
            'paid_fallback':False, 'observed_at':observed}


def claude_launch_check(*, auth, route, review, accepted_seat_limit, observed_at, now):
    observed = _fresh(observed_at, now)
    _route(route, 'anthropic')
    if not isinstance(auth, dict) or auth.get('loggedIn') is not True:
        raise RecordError('native Claude login required')
    # Match Rad's retained ON policy/checklist v3.1, not a command to enable
    # paid usage: drawer_07d5151703d16c043e02fb7479f78ba1, renewed in
    # drawer_773843c44471103f3cd0f94acfc75cde. A changed setting needs a new
    # trusted policy observation; this function never modifies an account.
    if (not isinstance(review, dict) or review.get('billing_month') != now.strftime('%Y-%m')
            or not isinstance(review.get('source'), str) or not review['source'].strip()
            or not _number(accepted_seat_limit) or accepted_seat_limit <= 0
            or not _number(review.get('seat_limit'))
            or review['seat_limit'] != accepted_seat_limit
            or review.get('extra_usage_enabled') is not True
            or not _number(review.get('reviewed_mtd'))
            or not 0 <= review['reviewed_mtd'] < accepted_seat_limit
            or review['reviewed_mtd'] > 0 and review.get('positive_spend_reviewed') is not True):
        raise RecordError('accepted seat-cap admin review required')
    return {'provider':'anthropic', 'billing_policy':'seat-cap-admin-review',
            'numeric_allowance':None, 'seat_limit':accepted_seat_limit,
            'reviewed_mtd':review['reviewed_mtd'], 'review_source':review['source'],
            'billing_month':review['billing_month'], 'observed_at':observed}
