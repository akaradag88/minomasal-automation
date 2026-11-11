"""Read-only Cloudflare usage helpers. No inference and no credential logging."""
from datetime import datetime, timezone
import math
from minomasal_images import ProviderFailure, json_response

ROOT='https://api.cloudflare.com/client/v4'
FREE_NEURONS=10_000

def number(value):
    return type(value) in (int,float) and math.isfinite(value) and value>=0

def query_quota(account,token,transport=None):
    if transport is None:
        from minomasal_images import http as transport
    now=datetime.now(timezone.utc)
    start=now.replace(hour=0,minute=0,second=0,microsecond=0).isoformat().replace('+00:00','Z')
    end=now.isoformat().replace('+00:00','Z')
    # Account is validated hex and timestamps are generated locally. No arbitrary
    # queries/URLs/user input, model filter or dimensions that could omit usage.
    query=('query { viewer { accounts(filter: {accountTag: "'+account+'"}) { '
           'aiInferenceAdaptiveGroups(limit: 1, filter: {datetime_geq: "'+start+'", datetime_lt: "'+end+'"}) '
           '{ sum { totalNeurons } } } } }')
    payload=json_response(transport('cloudflare','POST',ROOT+'/graphql',
                              headers={'Authorization':'Bearer '+token},json={'query':query}), 'cloudflare')
    if payload.get('errors'):
        raise ProviderFailure('cloudflare','quota_query_denied_or_unsupported')
    try:
        accounts=payload['data']['viewer']['accounts']
        if not isinstance(accounts,list) or len(accounts)!=1:raise ValueError()
        groups=accounts[0]['aiInferenceAdaptiveGroups']
        if not isinstance(groups,list) or len(groups)>1:raise ValueError()
        used=groups[0]['sum']['totalNeurons'] if groups else 0
        if not number(used):raise ValueError()
    except (KeyError,TypeError,ValueError):
        raise ProviderFailure('cloudflare','quota_response_unverified') from None
    return {'utc_day':now.date().isoformat(),'used_neurons_reported':used,
            'free_daily_neurons':FREE_NEURONS,'remaining_neurons_reported':max(0,FREE_NEURONS-used),
            'source':'account_all_models_graphql','analytics_may_lag':True,
            'authoritative_remaining_quota':False}

