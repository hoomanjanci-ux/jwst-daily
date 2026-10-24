"""Pure, persistent adaptive analysis cadence. UTC internally; no external calls.
A healthy reserve shortens the gap; scarce supply stretches it, never lowering quality.
GitHub cron is only a wake-up signal, not permission to publish a burst.
"""
from datetime import datetime, timedelta, timezone


def parse(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
    except (ValueError, TypeError):
        return None


def publication_times(state):
    return sorted(t for r in state.get('products', {}).values()
                  if any(r.get('channels', {}).get(k) == 'sent' for k in ('fa_ai', 'en_ai'))
                  and (t := parse(r.get('published_utc'))) is not None)


def plan(state, ready, now=None):
    now = now or datetime.now(timezone.utc)
    times = publication_times(state)
    interval = 4 if ready >= 5 else 6 if ready >= 3 else 8
    due = times[-1] + timedelta(hours=interval) if times else now
    recent = [t for t in times if t > now - timedelta(hours=24)]
    if len(recent) >= 4:
        due = max(due, recent[-4] + timedelta(hours=24))
    attempt = parse(state.get('analysis_publish_attempt_utc'))
    if attempt:
        due = max(due, attempt + timedelta(hours=1))
    refill = parse(state.get('analysis_refill_attempt_utc'))
    usage = state.get('analysis_byte_budget', {})
    spent = int(usage.get('bytes', 0)) if usage.get('day') == now.date().isoformat() else 0
    remaining = max(0, 900_000_000 - spent)
    return {'ready': ready, 'interval_hours': interval,
            'publish_due': ready > 0 and now >= due,
            'next_publish_not_before_utc': due.isoformat() if ready else None,
            'refill_due': ready < 4 and remaining > 0 and
                          (refill is None or now - refill >= timedelta(hours=4)),
            'remaining_batch_bytes': remaining,
            'daily_limit': 4}


def account_bytes(state, count, now=None):
    now = now or datetime.now(timezone.utc)
    day = now.date().isoformat()
    usage = state.setdefault('analysis_byte_budget', {})
    if usage.get('day') != day:
        usage.update(day=day, bytes=0)
    usage['bytes'] = int(usage.get('bytes', 0)) + int(count)
