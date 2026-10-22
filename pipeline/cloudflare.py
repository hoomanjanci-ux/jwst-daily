"""
cloudflare.py - D1 (Serverless SQL) client, READY for the owner's Cloudflare token.

Owner plan (2026-10-22): he provisions Cloudflare (login/token) + free AI APIs, THEN
we activate quality tooling. This client is written and unit-tested NOW so activation
is zero-code: set 3 env vars and everything below comes alive.

Env (GitHub Secrets, registered the day the owner sends them):
  CF_ACCOUNT_ID       dashboard -> Workers & Pages -> Account ID (32 hex)
  CF_API_TOKEN        template "D1 Edit" (or custom: Account/D1:Edit), scoped to one account
  CF_D1_DATABASE_ID   created once via `wrangler d1 create jwst-memory` or REST (helper below)

Free-tier headroom (official quotas): 5M reads + 100k writes per DAY, 5GB storage.
Our text-memory workload (<= a few hundred rows/day) uses <0.1% of it.

Design: every function returns (ok, detail) and NEVER raises - the pipeline must run
with or without Cloudflare configured (graceful degradation to repo-only memory).
"""
from __future__ import annotations

import json
import os

import requests

API_BASE = "https://api.cloudflare.com/client/v4"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS analyses (
  product      TEXT PRIMARY KEY,
  published_at TEXT,
  target       TEXT,
  instrument   TEXT,
  filter       TEXT,
  proposal     TEXT,
  score_h      REAL,
  score_ai     REAL,
  channels     TEXT,
  payload      TEXT
);
CREATE TABLE IF NOT EXISTS quality_log (
  product    TEXT,
  ts         TEXT,
  kind       TEXT,
  score      REAL,
  detail     TEXT
);
"""


def _cfg():
    acct = (os.environ.get("CF_ACCOUNT_ID", "") or "").strip()
    tok = (os.environ.get("CF_API_TOKEN", "") or "").strip()
    dbid = (os.environ.get("CF_D1_DATABASE_ID", "") or "").strip()
    return acct, tok, dbid


def configured() -> bool:
    a, t, d = _cfg()
    return bool(a and t and d)


def _req(method, path, token, **kw):
    try:
        r = requests.request(method, API_BASE + path,
                             headers={"Authorization": f"Bearer {token}"}, timeout=30, **kw)
        data = r.json()
        return (r.status_code == 200 and data.get("success") is True), data
    except Exception as e:  # noqa: BLE001
        return False, {"error": f"{type(e).__name__}: {e}"}


def probe() -> tuple[bool, str]:
    """First live test once the owner's token arrives: token validity + D1 reach.
    Works with token only (account id optional for /user/tokens/verify)."""
    _, tok, _ = _cfg()
    if not tok:
        return False, "CF_API_TOKEN not set"
    ok, data = _req("GET", "/user/tokens/verify", tok)
    if not ok:
        return False, f"token verify failed: {json.dumps(data)[:200]}"
    return True, "token valid"


def d1_query(sql, params=None) -> tuple[bool, object]:
    """Run one statement on the configured D1 database. Returns (ok, result|error)."""
    acct, tok, dbid = _cfg()
    if not (acct and tok and dbid):
        return False, "cloudflare not configured"
    ok, data = _req("POST", f"/accounts/{acct}/d1/database/{dbid}/query", tok,
                    json={"sql": sql, "params": params or []})
    if not ok:
        return False, data
    return True, data.get("result")


def ensure_schema() -> tuple[bool, str]:
    ok, res = d1_query(SCHEMA_SQL)
    return ok, ("schema ok" if ok else json.dumps(res)[:200])


def create_database(name="jwst-memory") -> tuple[bool, str]:
    """One-time helper (run locally/sandbox with the owner token): create the DB."""
    acct, tok, _ = _cfg()
    if not (acct and tok):
        return False, "need CF_ACCOUNT_ID + CF_API_TOKEN"
    ok, data = _req("POST", f"/accounts/{acct}/d1/database", tok,
                    json={"name": name})
    if not ok:
        return False, json.dumps(data)[:300]
    return True, data.get("result", {}).get("uuid", "")


def sync_analysis(product: str, published_at: str, meta: dict, score_h: float,
                  score_ai: float | None, channels: dict, payload_path: str) -> tuple[bool, str]:
    """Mirror one analysis row into D1 (repo stays source of truth; D1 = queryable mirror)."""
    ok, res = d1_query(
        "INSERT INTO analyses (product,published_at,target,instrument,filter,proposal,"
        "score_h,score_ai,channels,payload) VALUES (?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(product) DO UPDATE SET published_at=excluded.published_at,"
        "score_h=excluded.score_h,score_ai=excluded.score_ai,channels=excluded.channels,"
        "payload=excluded.payload",
        [product, published_at, str(meta.get("TARGNAME") or ""), str(meta.get("INSTRUME") or ""),
         str(meta.get("FILTER") or ""), str(meta.get("PROPOSID") or ""),
         score_h, score_ai, json.dumps(channels, ensure_ascii=False), payload_path])
    return ok, ("synced" if ok else json.dumps(res)[:200])
