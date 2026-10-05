"""Conservative peer comparisons; sparse/missing metadata stays explicitly unadjusted."""
from datetime import datetime, timezone
from statistics import median
from content_policy import excluded, classify


def duration_band(seconds):
    if not seconds or seconds < 0: return None
    if seconds <= 180: return 'up_to_3_minutes'
    if seconds <= 1200: return '3_to_20_minutes'
    return 'over_20_minutes'


def age_band(entry, now):
    value=entry.get('upload_date')
    try:
        date=datetime.strptime(value,'%Y%m%d').replace(tzinfo=timezone.utc)
    except (ValueError,TypeError): return None
    days=(now-date).total_seconds()/86400
    if days<0: return None
    return '0_to_7_days' if days<=7 else '8_to_30_days' if days<=30 else '31_to_90_days' if days<=90 else 'over_90_days'


def score_entries(entries, now=None):
    now=now or datetime.now(timezone.utc)
    eligible=[e for e in entries if (e.get('view_count') or 0)>0 and not excluded(e)]
    raw_baseline=max(1000.0,float(median(e['view_count'] for e in eligible))) if eligible else 1000.0
    scores={}
    for entry in entries:
        band=duration_band(entry.get('duration'))
        age=age_band(entry,now)
        kind=classify(entry.get('title',''))['contentType']
        peers=[p for p in eligible if band and age and duration_band(p.get('duration'))==band
               and age_band(p,now)==age and classify(p.get('title',''))['contentType']==kind]
        adjusted=len(peers)>=5
        baseline=max(1000.0,float(median(p['view_count'] for p in peers))) if adjusted else raw_baseline
        scores[entry.get('id')]={
            'baselineViews':baseline,'outlierScore':round((entry.get('view_count') or 0)/baseline,2),
            'baselineSampleSize':len(peers) if adjusted else len(eligible),
            'scoreBasis':'matched_age_duration_content' if adjusted else 'unadjusted_channel_sample',
            'scoreVersion':'peer-bands-v1','durationBand':band or 'unknown','ageBand':age or 'unknown',
            'scoreCaution':'Observational comparison, not causal evidence. Minimum baseline is 1,000 views.' if adjusted
                else 'Insufficient comparable age/duration metadata or fewer than five peers; score is NOT age/format adjusted.'}
    return scores
