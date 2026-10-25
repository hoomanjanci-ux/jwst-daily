"""Four independent Tehran calendar slots. No rolling cap or adaptive spacing.
Outside-window cron delays are recorded as missed; never dumped as catch-up posts.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TEHRAN = ZoneInfo('Asia/Tehran')
HOURS = (6, 9, 12, 18)

def windows(now=None):
    local = (now or datetime.now(timezone.utc)).astimezone(TEHRAN)
    return [(f'{local.date().isoformat()}/{hour:02d}',
             local.replace(hour=hour,minute=0,second=0,microsecond=0),
             local.replace(hour=hour+1,minute=0,second=0,microsecond=0)) for hour in HOURS]

def current(now=None):
    now = (now or datetime.now(timezone.utc)).astimezone(TEHRAN)
    return next(((key,start,end) for key,start,end in windows(now) if start<=now<end),None)

def next_window(now=None):
    now = (now or datetime.now(timezone.utc)).astimezone(TEHRAN)
    for day in (now, now+timedelta(days=1)):
        for key,start,end in windows(day):
            if start>now:return key,start,end

def refresh(state, now=None):
    now=(now or datetime.now(timezone.utc)).astimezone(TEHRAN)
    slots=state.setdefault('analysis_slots',{})
    # Audit expired records (also across midnight), never silently recycle them.
    for rec in slots.values():
        end=datetime.fromisoformat(rec['end'])
        if now>=end and rec['status'] not in ('sent','missed','unverified'):
            rec['status']='missed' if not rec.get('product') else 'partial_expired'
    for key,start,end in windows(now):
        slots.setdefault(key,{'start':start.isoformat(),'end':end.isoformat(),
                              'status':'missed' if now>=end else 'waiting'})
    cutoff=(now-timedelta(days=45)).date().isoformat()
    for key in list(slots):
        if key.split('/')[0]<cutoff:del slots[key]
    active=current(now)
    return (active[0],slots[active[0]]) if active else (None,None)
