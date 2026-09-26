"""
Local storage for MailBlaster (SQLite). Contacts, groups, sender accounts
(incl. IMAP + warm-up), campaigns (A/B + follow-ups), the per-recipient send
log, open/click/unsub events, the unified inbox (replies, auto-replies,
bounces), bounce records and a permanent suppression list. All local.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sqlite3
import threading
import time

_LOCK = threading.RLock()
_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mailblaster.db")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GROUP_COLORS = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
                "#ec4899", "#14b8a6", "#f97316", "#64748b"]

DEFAULT_SETTINGS = {
    "track_base": "", "track_mode": "", "sending_window_start": "0", "sending_window_end": "24",
    # safety brakes
    "brake_enabled": "1", "brake_bounce_pct": "5", "brake_min_sample": "50",
    "brake_fail_pct": "30", "brake_consec_fail": "10", "brake_complaints": "3",
    "brake_unsub_pct": "5",
    # bounce / reply processing
    "imap_interval_min": "5", "soft_bounce_limit": "3",
    "stop_followups_on_reply": "1", "auto_unsub_on_request": "1",
}


def set_db_path(path: str):
    global _DB_PATH
    _DB_PATH = path


def _conn():
    c = sqlite3.connect(_DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    return c


def _cols(c, table):
    return {r["name"] for r in c.execute(f"PRAGMA table_info({table})")}


def _add_cols(c, table, cols):
    have = _cols(c, table)
    for name, decl in cols:
        if name not in have:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


def init():
    with _LOCK, _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS contacts(
                id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL,
                first_name TEXT DEFAULT '', last_name TEXT DEFAULT '',
                data TEXT DEFAULT '{}', status TEXT DEFAULT 'active', created_at REAL);
            CREATE TABLE IF NOT EXISTS lists(
                id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, created_at REAL);
            CREATE TABLE IF NOT EXISTS list_members(
                list_id INTEGER, contact_id INTEGER, UNIQUE(list_id, contact_id));
            CREATE TABLE IF NOT EXISTS accounts(
                id INTEGER PRIMARY KEY, label TEXT, host TEXT, port INTEGER, security TEXT,
                username TEXT, password TEXT, from_name TEXT, from_email TEXT, reply_to TEXT,
                daily_limit INTEGER DEFAULT 500, sent_today INTEGER DEFAULT 0,
                day TEXT DEFAULT '', active INTEGER DEFAULT 1, created_at REAL);
            CREATE TABLE IF NOT EXISTS campaigns(
                id INTEGER PRIMARY KEY, name TEXT, subject TEXT, subject_b TEXT DEFAULT '',
                html TEXT, text TEXT, list_id INTEGER, account_ids TEXT DEFAULT '[]',
                track_opens INTEGER DEFAULT 1, track_clicks INTEGER DEFAULT 1,
                rate INTEGER DEFAULT 60, jitter REAL DEFAULT 2,
                parent_id INTEGER DEFAULT 0, step_no INTEGER DEFAULT 0,
                send_to TEXT DEFAULT 'all', scheduled_at REAL DEFAULT 0,
                status TEXT DEFAULT 'draft', created_at REAL,
                sent INTEGER DEFAULT 0, failed INTEGER DEFAULT 0, skipped INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS sends(
                id INTEGER PRIMARY KEY, campaign_id INTEGER, contact_id INTEGER,
                email TEXT, status TEXT, variant TEXT DEFAULT 'A', error TEXT, sent_at REAL);
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY, campaign_id INTEGER, contact_id INTEGER,
                type TEXT, url TEXT, ts REAL);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS inbox(
                id INTEGER PRIMARY KEY, account_id INTEGER, contact_id INTEGER DEFAULT 0,
                campaign_id INTEGER DEFAULT 0, kind TEXT, from_email TEXT, from_name TEXT,
                subject TEXT, snippet TEXT, body TEXT, received_at REAL, message_id TEXT,
                references_ TEXT DEFAULT '', is_read INTEGER DEFAULT 0, label TEXT DEFAULT '',
                archived INTEGER DEFAULT 0, created_at REAL,
                UNIQUE(account_id, message_id));
            CREATE TABLE IF NOT EXISTS bounces(
                id INTEGER PRIMARY KEY, contact_id INTEGER DEFAULT 0, email TEXT,
                campaign_id INTEGER DEFAULT 0, kind TEXT, code TEXT, reason TEXT,
                source TEXT, ts REAL);
            CREATE TABLE IF NOT EXISTS suppression(
                email TEXT PRIMARY KEY, reason TEXT, ts REAL);
        """)
        _add_cols(c, "contacts", [("replied_at", "REAL DEFAULT 0"),
                                  ("soft_bounces", "INTEGER DEFAULT 0"),
                                  ("status_reason", "TEXT DEFAULT ''")])
        _add_cols(c, "lists", [("color", "TEXT DEFAULT ''")])
        _add_cols(c, "accounts", [
            ("imap_enabled", "INTEGER DEFAULT 0"), ("imap_host", "TEXT DEFAULT ''"),
            ("imap_port", "INTEGER DEFAULT 993"), ("imap_security", "TEXT DEFAULT 'ssl'"),
            ("imap_user", "TEXT DEFAULT ''"), ("imap_password", "TEXT DEFAULT ''"),
            ("imap_folders", "TEXT DEFAULT 'INBOX'"), ("imap_state", "TEXT DEFAULT '{}'"),
            ("imap_last_check", "REAL DEFAULT 0"), ("imap_error", "TEXT DEFAULT ''"),
            ("warmup_enabled", "INTEGER DEFAULT 0"), ("warmup_start", "INTEGER DEFAULT 20"),
            ("warmup_growth", "REAL DEFAULT 20"), ("warmup_started", "TEXT DEFAULT ''"),
            ("paused_reason", "TEXT DEFAULT ''")])
        _add_cols(c, "campaigns", [("group_ids", "TEXT DEFAULT '[]'"),
                                   ("exclude_group_ids", "TEXT DEFAULT '[]'"),
                                   ("brakes", "INTEGER DEFAULT 1"),
                                   ("brake_reason", "TEXT DEFAULT ''"),
                                   ("bounced", "INTEGER DEFAULT 0"),
                                   ("tracking", "TEXT DEFAULT ''")])
        _add_cols(c, "sends", [("message_id", "TEXT DEFAULT ''"),
                               ("account_id", "INTEGER DEFAULT 0")])
        c.executescript("""
            CREATE INDEX IF NOT EXISTS idx_sends_c ON sends(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_sends_ct ON sends(contact_id);
            CREATE INDEX IF NOT EXISTS idx_sends_mid ON sends(message_id);
            CREATE INDEX IF NOT EXISTS idx_sends_email ON sends(email);
            CREATE INDEX IF NOT EXISTS idx_sends_ts ON sends(sent_at);
            CREATE INDEX IF NOT EXISTS idx_ev_c ON events(campaign_id);
            CREATE INDEX IF NOT EXISTS idx_ev_ct ON events(contact_id);
            CREATE INDEX IF NOT EXISTS idx_lm ON list_members(list_id);
            CREATE INDEX IF NOT EXISTS idx_lm_c ON list_members(contact_id);
            CREATE INDEX IF NOT EXISTS idx_ct_status ON contacts(status);
            CREATE INDEX IF NOT EXISTS idx_inbox_ts ON inbox(received_at);
            CREATE INDEX IF NOT EXISTS idx_bounce_c ON bounces(campaign_id);
        """)
        # a campaign can't be "running" at startup: the process that ran it is gone
        c.execute("UPDATE campaigns SET status='interrupted' WHERE status='running'")


# --------------------------- settings --------------------------------------- #
def get_settings():
    with _LOCK, _conn() as c:
        st = {r["key"]: r["value"] for r in c.execute("SELECT key,value FROM settings")}
    out = dict(DEFAULT_SETTINGS)
    out.update(st)
    return out


def setting_num(st, key, default=0.0):
    try:
        return float(st.get(key, default))
    except (TypeError, ValueError):
        return float(default)


def save_settings(d):
    with _LOCK, _conn() as c:
        for k, v in d.items():
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))


# --------------------------- sender accounts -------------------------------- #
_ACC_FIELDS = ["label", "host", "port", "security", "username", "password", "from_name",
               "from_email", "reply_to", "daily_limit", "active",
               "imap_enabled", "imap_host", "imap_port", "imap_security", "imap_user",
               "imap_password", "imap_folders",
               "warmup_enabled", "warmup_start", "warmup_growth"]
_ACC_INT = {"port", "daily_limit", "active", "imap_enabled", "imap_port", "warmup_enabled",
            "warmup_start"}


def _acc_val(k, v):
    if k in _ACC_INT:
        return int(float(v or 0))
    if k == "warmup_growth":
        return float(v or 0)
    return v


def add_account(d):
    row = {k: _acc_val(k, d[k]) for k in _ACC_FIELDS if k in d and d[k] not in (None, "")}
    row.setdefault("label", d.get("from_email", ""))
    row.setdefault("port", 587)
    row.setdefault("security", "starttls")
    row.setdefault("daily_limit", 500)
    row["active"] = 1
    row["created_at"] = time.time()
    if row.get("warmup_enabled"):
        row["warmup_started"] = time.strftime("%Y-%m-%d")
    keys = list(row)
    with _LOCK, _conn() as c:
        return c.execute(f"INSERT INTO accounts({','.join(keys)}) VALUES({','.join('?' * len(keys))})",
                         [row[k] for k in keys]).lastrowid


def update_account(aid, d):
    with _LOCK, _conn() as c:
        cur = c.execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone()
        if not cur:
            return
        row = {}
        for k in _ACC_FIELDS:
            if k not in d:
                continue
            v = d[k]
            if k in ("password", "imap_password") and not v:
                continue          # blank = keep the stored secret
            row[k] = _acc_val(k, v)
        # turning warm-up on (re)starts the ramp from day 1
        if row.get("warmup_enabled") and not cur["warmup_enabled"]:
            row["warmup_started"] = time.strftime("%Y-%m-%d")
        if row:
            c.execute(f"UPDATE accounts SET {','.join(k + '=?' for k in row)} WHERE id=?",
                      list(row.values()) + [aid])


def set_account_fields(aid, **kw):
    if not kw:
        return
    with _LOCK, _conn() as c:
        c.execute(f"UPDATE accounts SET {','.join(k + '=?' for k in kw)} WHERE id=?",
                  list(kw.values()) + [aid])


def restart_warmup(aid):
    set_account_fields(aid, warmup_enabled=1, warmup_started=time.strftime("%Y-%m-%d"))


def delete_account(aid):
    with _LOCK, _conn() as c:
        c.execute("DELETE FROM accounts WHERE id=?", (aid,))


def warmup_info(a):
    """Effective daily limit for today + the ramp schedule."""
    target = int(a.get("daily_limit") or 0)
    if not a.get("warmup_enabled") or not a.get("warmup_started"):
        return {"limit": target, "active": False}
    start = max(1, int(a.get("warmup_start") or 20))
    growth = max(0.0, float(a.get("warmup_growth") or 0)) / 100.0
    try:
        d0 = _dt.date.fromisoformat(a["warmup_started"])
    except ValueError:
        d0 = _dt.date.today()
    day = max(0, (_dt.date.today() - d0).days)

    def lim(n):
        return int(min(target, max(start, round(start * (1 + growth) ** n))))
    sched, n = [], 0
    while n < 120:
        v = lim(n)
        sched.append(v)
        if v >= target:
            break
        n += 1
    total_days = len(sched)
    today = lim(day)
    return {"limit": today, "active": True, "day": day + 1, "total_days": total_days,
            "done": today >= target, "schedule": sched[:60], "target": target, "start": start}


def _decorate_account(r, hide_pw=True):
    w = warmup_info(r)
    r["effective_limit"] = w["limit"]
    r["warmup"] = w
    try:
        r["imap_state"] = json.loads(r.get("imap_state") or "{}")
    except Exception:
        r["imap_state"] = {}
    if hide_pw:
        r["password"] = "••••" if r.get("password") else ""
        r["imap_password"] = "••••" if r.get("imap_password") else ""
    return r


def accounts(hide_pw=True):
    _roll_day()
    with _LOCK, _conn() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM accounts ORDER BY created_at")]
        since = time.time() - 7 * 86400
        stats = {r["account_id"]: dict(r) for r in c.execute(
            "SELECT account_id, SUM(status='sent') sent7, SUM(status='bounced') bounced7, "
            "SUM(status='failed') failed7 FROM sends WHERE sent_at>? GROUP BY account_id", (since,))}
    for r in rows:
        _decorate_account(r, hide_pw)
        s = stats.get(r["id"], {})
        r["sent7"] = s.get("sent7") or 0
        r["bounced7"] = s.get("bounced7") or 0
        r["failed7"] = s.get("failed7") or 0
    return rows


def get_account(aid):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone()
    return _decorate_account(dict(r), hide_pw=False) if r else None


def _roll_day():
    today = time.strftime("%Y-%m-%d")
    with _LOCK, _conn() as c:
        c.execute("UPDATE accounts SET sent_today=0, day=? WHERE day!=?", (today, today))


def accounts_for(ids):
    """Active, un-paused senders (selected ids, or all) with today's effective limit."""
    _roll_day()
    with _LOCK, _conn() as c:
        if ids:
            q = ",".join("?" * len(ids))
            rows = c.execute(f"SELECT * FROM accounts WHERE active=1 AND paused_reason='' "
                             f"AND id IN ({q}) ORDER BY sent_today ASC", ids).fetchall()
        else:
            rows = c.execute("SELECT * FROM accounts WHERE active=1 AND paused_reason='' "
                             "ORDER BY sent_today ASC").fetchall()
    return [_decorate_account(dict(r), hide_pw=False) for r in rows]


def incr_account(aid):
    with _LOCK, _conn() as c:
        c.execute("UPDATE accounts SET sent_today=sent_today+1, day=? WHERE id=?",
                  (time.strftime("%Y-%m-%d"), aid))


# --------------------------- groups ----------------------------------------- #
def create_group(name, color=""):
    name = (name or "").strip() or "My group"
    with _LOCK, _conn() as c:
        ex = c.execute("SELECT id FROM lists WHERE name=?", (name,)).fetchone()
        if ex:
            return ex["id"]
        if not color:
            n = c.execute("SELECT COUNT(*) FROM lists").fetchone()[0]
            color = GROUP_COLORS[n % len(GROUP_COLORS)]
        return c.execute("INSERT INTO lists(name,color,created_at) VALUES(?,?,?)",
                         (name, color, time.time())).lastrowid


create_list = create_group  # backwards compatibility


def update_group(gid, name=None, color=None):
    with _LOCK, _conn() as c:
        if name:
            name = name.strip()
            dup = c.execute("SELECT id FROM lists WHERE name=? AND id!=?", (name, gid)).fetchone()
            if dup:
                raise ValueError("A group with that name already exists.")
            c.execute("UPDATE lists SET name=? WHERE id=?", (name, gid))
        if color:
            c.execute("UPDATE lists SET color=? WHERE id=?", (color, gid))


def delete_group(gid, delete_contacts=False):
    with _LOCK, _conn() as c:
        removed = 0
        if delete_contacts:
            ids = [r[0] for r in c.execute("SELECT contact_id FROM list_members WHERE list_id=?",
                                           (gid,))]
            removed = _delete_contact_ids(c, ids)
        c.execute("DELETE FROM list_members WHERE list_id=?", (gid,))
        c.execute("DELETE FROM lists WHERE id=?", (gid,))
    return removed


def groups():
    with _LOCK, _conn() as c:
        rows = [dict(r) for r in c.execute(
            "SELECT l.id,l.name,l.color,l.created_at,"
            "(SELECT COUNT(*) FROM list_members m WHERE m.list_id=l.id) n,"
            "(SELECT COUNT(*) FROM list_members m JOIN contacts ct ON ct.id=m.contact_id "
            " WHERE m.list_id=l.id AND ct.status='active') active "
            "FROM lists l ORDER BY l.name COLLATE NOCASE")]
    for i, r in enumerate(rows):
        r["color"] = r.get("color") or GROUP_COLORS[i % len(GROUP_COLORS)]
    return rows


lists = groups


# --------------------------- suppression ------------------------------------ #
def suppress(c, email, reason):
    c.execute("INSERT INTO suppression(email,reason,ts) VALUES(?,?,?) "
              "ON CONFLICT(email) DO UPDATE SET reason=excluded.reason",
              ((email or "").strip().lower(), reason, time.time()))


def suppression_add(emails, reason="manual"):
    n = 0
    with _LOCK, _conn() as c:
        for e in emails:
            e = (e or "").strip().lower()
            if not EMAIL_RE.match(e):
                continue
            suppress(c, e, reason)
            status = "bounced" if reason == "bounce" else "unsubscribed"
            c.execute("UPDATE contacts SET status=?, status_reason=? WHERE email=?",
                      (status, reason, e))
            n += 1
    return n


def suppression_remove(emails):
    with _LOCK, _conn() as c:
        for e in emails:
            c.execute("DELETE FROM suppression WHERE email=?", ((e or "").strip().lower(),))


def suppression_list(q="", page=0, per=50):
    args, w = [], ""
    if q:
        w = "WHERE email LIKE ?"
        args.append(f"%{q.lower()}%")
    with _LOCK, _conn() as c:
        total = c.execute(f"SELECT COUNT(*) FROM suppression {w}", args).fetchone()[0]
        rows = [dict(r) for r in c.execute(
            f"SELECT email,reason,ts FROM suppression {w} ORDER BY ts DESC LIMIT ? OFFSET ?",
            args + [per, page * per])]
    return {"total": total, "rows": rows, "page": page, "per": per}


def suppression_csv():
    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["email", "reason", "date"])
    with _LOCK, _conn() as c:
        for r in c.execute("SELECT email,reason,ts FROM suppression ORDER BY ts DESC"):
            w.writerow([r["email"], r["reason"], time.strftime("%Y-%m-%d", time.localtime(r["ts"]))])
    return out.getvalue()


# --------------------------- contacts --------------------------------------- #
def add_contact(email, first="", last="", data=None, list_id=None):
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        return None
    with _LOCK, _conn() as c:
        ex = c.execute("SELECT id FROM contacts WHERE email=?", (email,)).fetchone()
        if ex:
            cid = ex["id"]
        else:
            sup = c.execute("SELECT reason FROM suppression WHERE email=?", (email,)).fetchone()
            status = ("bounced" if sup["reason"] == "bounce" else "unsubscribed") if sup else "active"
            cid = c.execute("INSERT INTO contacts(email,first_name,last_name,data,status,"
                            "status_reason,created_at) VALUES(?,?,?,?,?,?,?)",
                            (email, first, last, json.dumps(data or {}), status,
                             sup["reason"] if sup else "", time.time())).lastrowid
        if list_id:
            c.execute("INSERT OR IGNORE INTO list_members(list_id,contact_id) VALUES(?,?)",
                      (list_id, cid))
    return cid


def import_contacts(rows, list_id):
    added = updated = skipped = invalid = suppressed = 0
    seen = set()
    with _LOCK, _conn() as c:
        existing = {r[1]: r[0] for r in c.execute("SELECT id,email FROM contacts")}
        sup = {r[0]: r[1] for r in c.execute("SELECT email,reason FROM suppression")}
        now = time.time()
        for r in rows:
            email = (r.get("email") or "").strip().lower()
            if not email or not EMAIL_RE.match(email):
                invalid += 1
                continue
            if email in seen:
                skipped += 1
                continue
            seen.add(email)
            extra = {k: v for k, v in r.items()
                     if k not in ("email", "first_name", "last_name") and v not in (None, "")}
            fn = (r.get("first_name") or "").strip()
            ln = (r.get("last_name") or "").strip()
            cid = existing.get(email)
            if cid:
                c.execute("UPDATE contacts SET first_name=COALESCE(NULLIF(?,''),first_name),"
                          "last_name=COALESCE(NULLIF(?,''),last_name),data=? WHERE id=?",
                          (fn, ln, json.dumps(extra), cid))
                updated += 1
            else:
                reason = sup.get(email)
                status = ("bounced" if reason == "bounce" else "unsubscribed") if reason else "active"
                if reason:
                    suppressed += 1
                cid = c.execute("INSERT INTO contacts(email,first_name,last_name,data,status,"
                                "status_reason,created_at) VALUES(?,?,?,?,?,?,?)",
                                (email, fn, ln, json.dumps(extra), status, reason or "",
                                 now)).lastrowid
                existing[email] = cid
                added += 1
            if list_id:
                c.execute("INSERT OR IGNORE INTO list_members(list_id,contact_id) VALUES(?,?)",
                          (list_id, cid))
    return {"added": added, "updated": updated, "skipped_dupes": skipped, "invalid": invalid,
            "suppressed": suppressed}


def contact_stats():
    with _LOCK, _conn() as c:
        by = {r[0]: r[1] for r in c.execute("SELECT status,COUNT(*) FROM contacts GROUP BY status")}
        replied = c.execute("SELECT COUNT(*) FROM contacts WHERE replied_at>0").fetchone()[0]
        ungrouped = c.execute("SELECT COUNT(*) FROM contacts WHERE id NOT IN "
                              "(SELECT contact_id FROM list_members)").fetchone()[0]
    return {"total": sum(by.values()), "active": by.get("active", 0),
            "unsubscribed": by.get("unsubscribed", 0), "bounced": by.get("bounced", 0),
            "invalid": by.get("invalid", 0), "replied": replied, "ungrouped": ungrouped}


def _contact_where(q="", status="", group=""):
    where, args = ["1=1"], []
    if status == "replied":
        where.append("c.replied_at>0")
    elif status:
        where.append("c.status=?")
        args.append(status)
    if group == "none":
        where.append("c.id NOT IN (SELECT contact_id FROM list_members)")
    elif str(group).isdigit():
        where.append("c.id IN (SELECT contact_id FROM list_members WHERE list_id=?)")
        args.append(int(group))
    q = (q or "").strip().lower()
    if q:
        where.append("(c.email LIKE ? OR LOWER(c.first_name) LIKE ? OR LOWER(c.last_name) LIKE ?)")
        args += [f"%{q}%"] * 3
    return " AND ".join(where), args


def search_contacts(q="", status="", page=0, per=50, group=""):
    w, args = _contact_where(q, status, group)
    per = max(10, min(int(per or 50), 500))
    with _LOCK, _conn() as c:
        total = c.execute(f"SELECT COUNT(*) FROM contacts c WHERE {w}", args).fetchone()[0]
        rows = [dict(r) for r in c.execute(
            f"SELECT c.id,c.email,c.first_name,c.last_name,c.status,c.status_reason,c.replied_at,"
            f"c.created_at FROM contacts c WHERE {w} ORDER BY c.created_at DESC, c.id DESC "
            "LIMIT ? OFFSET ?", args + [per, page * per])]
        if rows:
            ids = [r["id"] for r in rows]
            gm = {}
            for m in c.execute(f"SELECT m.contact_id,l.id,l.name,l.color FROM list_members m "
                               f"JOIN lists l ON l.id=m.list_id WHERE m.contact_id IN "
                               f"({','.join('?' * len(ids))})", ids):
                gm.setdefault(m[0], []).append({"id": m[1], "name": m[2], "color": m[3]})
            for r in rows:
                r["groups"] = gm.get(r["id"], [])
    return {"total": total, "rows": rows, "page": page, "per": per}


def contact_detail(cid):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT * FROM contacts WHERE id=?", (cid,)).fetchone()
        if not r:
            return None
        sends = [dict(x) for x in c.execute(
            "SELECT s.campaign_id,s.status,s.sent_at,s.error,c.name FROM sends s "
            "LEFT JOIN campaigns c ON c.id=s.campaign_id WHERE s.contact_id=? "
            "ORDER BY s.sent_at DESC LIMIT 50", (cid,))]
        events = [dict(x) for x in c.execute(
            "SELECT type,url,ts,campaign_id FROM events WHERE contact_id=? "
            "ORDER BY ts DESC LIMIT 50", (cid,))]
        replies = [dict(x) for x in c.execute(
            "SELECT id,kind,subject,snippet,received_at,label FROM inbox WHERE contact_id=? "
            "ORDER BY received_at DESC LIMIT 20", (cid,))]
        grp = [dict(x) for x in c.execute(
            "SELECT l.id,l.name,l.color FROM list_members m JOIN lists l ON l.id=m.list_id "
            "WHERE m.contact_id=?", (cid,))]
    d = dict(r)
    try:
        d["data"] = json.loads(d.get("data") or "{}")
    except Exception:
        d["data"] = {}
    d.update(sends=sends, events=events, replies=replies, groups=grp)
    return d


def _delete_contact_ids(c, ids):
    """Delete contacts, keeping unsubscribed/bounced addresses on the suppression list
    so a re-import can never email them again."""
    ids = list(ids)
    n = 0
    for i in range(0, len(ids), 800):
        chunk = ids[i:i + 800]
        q = ",".join("?" * len(chunk))
        for r in c.execute(f"SELECT email,status,status_reason FROM contacts WHERE id IN ({q}) "
                           "AND status IN ('unsubscribed','bounced')", chunk).fetchall():
            suppress(c, r["email"], "bounce" if r["status"] == "bounced"
                     else (r["status_reason"] or "unsubscribed"))
        n += c.execute(f"DELETE FROM contacts WHERE id IN ({q})", chunk).rowcount
        c.execute(f"DELETE FROM list_members WHERE contact_id IN ({q})", chunk)
    return n


def delete_contact(cid):
    with _LOCK, _conn() as c:
        _delete_contact_ids(c, [cid])


def delete_all_contacts():
    with _LOCK, _conn() as c:
        for r in c.execute("SELECT email,status,status_reason FROM contacts "
                           "WHERE status IN ('unsubscribed','bounced')").fetchall():
            suppress(c, r["email"], "bounce" if r["status"] == "bounced"
                     else (r["status_reason"] or "unsubscribed"))
        n = c.execute("DELETE FROM contacts").rowcount
        c.execute("DELETE FROM list_members")
    return n


def bulk_contacts(action, ids=None, filt=None, group_id=None):
    """Apply an action to explicit ids, or to everything matching a filter."""
    with _LOCK, _conn() as c:
        if filt is not None:
            w, args = _contact_where(filt.get("q", ""), filt.get("status", ""),
                                     filt.get("group", ""))
            ids = [r[0] for r in c.execute(f"SELECT c.id FROM contacts c WHERE {w}", args)]
        ids = [int(i) for i in (ids or [])]
        if not ids:
            return 0
        if action == "delete":
            return _delete_contact_ids(c, ids)
        n = 0
        for i in range(0, len(ids), 800):
            chunk = ids[i:i + 800]
            q = ",".join("?" * len(chunk))
            if action == "add_group" and group_id:
                c.executemany("INSERT OR IGNORE INTO list_members(list_id,contact_id) VALUES(?,?)",
                              [(group_id, x) for x in chunk])
                n += len(chunk)
            elif action == "remove_group" and group_id:
                n += c.execute(f"DELETE FROM list_members WHERE list_id=? AND contact_id IN ({q})",
                               [group_id] + chunk).rowcount
            elif action == "unsubscribe":
                for r in c.execute(f"SELECT email FROM contacts WHERE id IN ({q})", chunk).fetchall():
                    suppress(c, r["email"], "manual")
                n += c.execute(f"UPDATE contacts SET status='unsubscribed',status_reason='manual' "
                               f"WHERE id IN ({q})", chunk).rowcount
            elif action == "reactivate":   # only invalid ones — never override opt-outs
                n += c.execute(f"UPDATE contacts SET status='active',status_reason='' "
                               f"WHERE status='invalid' AND id IN ({q})", chunk).rowcount
        return n


def _recipient_sql(group_ids=None, exclude_ids=None):
    where, args = ["c.status='active'"], []
    if group_ids:
        where.append(f"c.id IN (SELECT contact_id FROM list_members WHERE list_id IN "
                     f"({','.join('?' * len(group_ids))}))")
        args += list(group_ids)
    if exclude_ids:
        where.append(f"c.id NOT IN (SELECT contact_id FROM list_members WHERE list_id IN "
                     f"({','.join('?' * len(exclude_ids))}))")
        args += list(exclude_ids)
    return " AND ".join(where), args


def recipient_count(group_ids=None, exclude_ids=None):
    w, args = _recipient_sql(group_ids, exclude_ids)
    with _LOCK, _conn() as c:
        return c.execute(f"SELECT COUNT(*) FROM contacts c WHERE {w}", args).fetchone()[0]


def recipients_for(group_ids=None, only=None, exclude_ids=None, exclude_group_ids=None):
    """Active recipients of the chosen groups (none = everyone), minus excluded groups.
    only: allowed contact ids (follow-ups); exclude_ids: contact ids to skip."""
    if isinstance(group_ids, int):
        group_ids = [group_ids]
    w, args = _recipient_sql(group_ids, exclude_group_ids)
    with _LOCK, _conn() as c:
        rows = c.execute(f"SELECT c.* FROM contacts c WHERE {w} ORDER BY c.id", args).fetchall()
    out = []
    ex = exclude_ids or set()
    for r in rows:
        if only is not None and r["id"] not in only:
            continue
        if r["id"] in ex:
            continue
        d = dict(r)
        try:
            d["data"] = json.loads(d.get("data") or "{}")
        except Exception:
            d["data"] = {}
        out.append(d)
    return out


def contact_status(cid):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT status FROM contacts WHERE id=?", (cid,)).fetchone()
    return r["status"] if r else "deleted"


def all_active_emails():
    with _LOCK, _conn() as c:
        return [(r["id"], r["email"]) for r in
                c.execute("SELECT id,email FROM contacts WHERE status='active'")]


def find_contact(email):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT * FROM contacts WHERE email=?", ((email or "").strip().lower(),)).fetchone()
    return dict(r) if r else None


def unsubscribe(email, reason="unsubscribed"):
    email = (email or "").strip().lower()
    with _LOCK, _conn() as c:
        suppress(c, email, reason)
        return c.execute("UPDATE contacts SET status='unsubscribed', status_reason=? WHERE email=?",
                         (reason, email)).rowcount > 0


def unsubscribe_by_id(cid, reason="unsubscribed"):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT email FROM contacts WHERE id=?", (cid,)).fetchone()
        if not r:
            return False
        suppress(c, r["email"], reason)
        return c.execute("UPDATE contacts SET status='unsubscribed', status_reason=? WHERE id=?",
                         (reason, cid)).rowcount > 0


def set_status(cid, status, reason=""):
    with _LOCK, _conn() as c:
        c.execute("UPDATE contacts SET status=?, status_reason=? WHERE id=?", (status, reason, cid))


def export_contacts_csv(filt=None):
    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["email", "first_name", "last_name", "status", "groups"])
    filt = filt or {}
    wh, args = _contact_where(filt.get("q", ""), filt.get("status", ""), filt.get("group", ""))
    with _LOCK, _conn() as c:
        for r in c.execute(
                f"SELECT c.email,c.first_name,c.last_name,c.status,"
                f"(SELECT GROUP_CONCAT(l.name,'; ') FROM list_members m JOIN lists l "
                f" ON l.id=m.list_id WHERE m.contact_id=c.id) g FROM contacts c WHERE {wh}", args):
            w.writerow([r["email"], r["first_name"], r["last_name"], r["status"], r["g"] or ""])
    return out.getvalue()


# --------------------------- bounces ---------------------------------------- #
def record_bounce(email, kind, code="", reason="", source="smtp", campaign_id=0, contact_id=0,
                  soft_limit=3):
    """kind: hard | soft | complaint. Updates the contact + suppression list."""
    email = (email or "").strip().lower()
    with _LOCK, _conn() as c:
        ct = None
        if contact_id:
            ct = c.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()
        if not ct and email:
            ct = c.execute("SELECT * FROM contacts WHERE email=?", (email,)).fetchone()
        cid = ct["id"] if ct else 0
        if not campaign_id and email:
            s = c.execute("SELECT campaign_id FROM sends WHERE email=? ORDER BY sent_at DESC LIMIT 1",
                          (email,)).fetchone()
            campaign_id = s["campaign_id"] if s else 0
        # de-dupe: the same bounce reported by SMTP and later by a DSN email
        dup = c.execute("SELECT id FROM bounces WHERE email=? AND campaign_id=? AND kind=? AND ts>?",
                        (email, campaign_id, kind, time.time() - 3 * 86400)).fetchone()
        if dup:
            return {"duplicate": True, "contact_id": cid, "campaign_id": campaign_id}
        c.execute("INSERT INTO bounces(contact_id,email,campaign_id,kind,code,reason,source,ts) "
                  "VALUES(?,?,?,?,?,?,?,?)",
                  (cid, email, campaign_id, kind, code, (reason or "")[:500], source, time.time()))
        if kind == "hard":
            suppress(c, email, "bounce")
            if cid:
                c.execute("UPDATE contacts SET status='bounced', status_reason=? WHERE id=?",
                          ((f"{code} {reason}".strip())[:200], cid))
        elif kind == "complaint":
            suppress(c, email, "complaint")
            if cid:
                c.execute("UPDATE contacts SET status='unsubscribed', status_reason='complaint' "
                          "WHERE id=?", (cid,))
        elif kind == "soft" and cid:
            n = (ct["soft_bounces"] or 0) + 1
            c.execute("UPDATE contacts SET soft_bounces=? WHERE id=?", (n, cid))
            if n >= soft_limit:
                suppress(c, email, "bounce")
                c.execute("UPDATE contacts SET status='bounced', status_reason=? WHERE id=?",
                          (f"{n} soft bounces", cid))
        if campaign_id and kind in ("hard", "soft"):
            c.execute("UPDATE campaigns SET bounced=(SELECT COUNT(*) FROM bounces WHERE "
                      "campaign_id=? AND kind='hard') WHERE id=?", (campaign_id, campaign_id))
    return {"duplicate": False, "contact_id": cid, "campaign_id": campaign_id}


def campaign_health(cid):
    """Counts the safety brakes look at."""
    with _LOCK, _conn() as c:
        hard = c.execute("SELECT COUNT(*) FROM bounces WHERE campaign_id=? AND kind='hard'",
                         (cid,)).fetchone()[0]
        compl = c.execute("SELECT COUNT(*) FROM bounces WHERE campaign_id=? AND kind='complaint'",
                          (cid,)).fetchone()[0]
        unsub = c.execute("SELECT COUNT(DISTINCT contact_id) FROM events WHERE campaign_id=? "
                          "AND type='unsub'", (cid,)).fetchone()[0]
    return {"hard": hard, "complaints": compl, "unsubs": unsub}


def recent_bounces(limit=100, q=""):
    args, w = [], ""
    if q:
        w = "WHERE b.email LIKE ?"
        args.append(f"%{q.lower()}%")
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(
            f"SELECT b.*, c.name campaign FROM bounces b LEFT JOIN campaigns c ON c.id=b.campaign_id "
            f"{w} ORDER BY b.ts DESC LIMIT ?", args + [limit])]


def deliverability_stats(days=30):
    since = time.time() - days * 86400
    with _LOCK, _conn() as c:
        sent = c.execute("SELECT COUNT(*) FROM sends WHERE status IN ('sent','bounced') AND sent_at>?",
                         (since,)).fetchone()[0]
        by = {r[0]: r[1] for r in c.execute(
            "SELECT kind,COUNT(*) FROM bounces WHERE ts>? GROUP BY kind", (since,))}
        replies = c.execute("SELECT COUNT(*) FROM inbox WHERE kind='reply' AND received_at>?",
                            (since,)).fetchone()[0]
        unsubs = c.execute("SELECT COUNT(DISTINCT contact_id) FROM events WHERE type='unsub' "
                           "AND ts>?", (since,)).fetchone()[0]
        suppressed = c.execute("SELECT COUNT(*) FROM suppression").fetchone()[0]
    hard = by.get("hard", 0)

    def pct(n):
        return round(n / sent * 100, 2) if sent else 0
    return {"days": days, "sent": sent, "hard": hard, "soft": by.get("soft", 0),
            "complaints": by.get("complaint", 0), "replies": replies, "unsubs": unsubs,
            "bounce_rate": pct(hard), "complaint_rate": pct(by.get("complaint", 0)),
            "reply_rate": pct(replies), "unsub_rate": pct(unsubs), "suppressed": suppressed}


# --------------------------- inbox ------------------------------------------ #
def find_send_by_msgids(mids):
    mids = [m.strip() for m in mids if m and m.strip()]
    if not mids:
        return None
    with _LOCK, _conn() as c:
        q = ",".join("?" * len(mids))
        r = c.execute(f"SELECT campaign_id,contact_id,account_id,email FROM sends "
                      f"WHERE message_id IN ({q}) ORDER BY sent_at DESC LIMIT 1", mids).fetchone()
    return dict(r) if r else None


def last_send_to(email):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT campaign_id,contact_id,account_id FROM sends WHERE email=? AND "
                      "status='sent' ORDER BY sent_at DESC LIMIT 1",
                      ((email or "").lower(),)).fetchone()
    return dict(r) if r else None


def inbox_add(d):
    with _LOCK, _conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO inbox(account_id,contact_id,campaign_id,kind,from_email,from_name,"
            "subject,snippet,body,received_at,message_id,references_,is_read,label,created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d.get("account_id", 0), d.get("contact_id", 0), d.get("campaign_id", 0), d["kind"],
             d.get("from_email", ""), d.get("from_name", ""), d.get("subject", ""),
             d.get("snippet", ""), d.get("body", ""), d.get("received_at") or time.time(),
             d.get("message_id", ""), d.get("references", ""), int(d.get("is_read", 0)),
             d.get("label", ""), time.time()))
        if cur.rowcount and d["kind"] == "reply" and d.get("contact_id"):
            c.execute("UPDATE contacts SET replied_at=? WHERE id=?",
                      (d.get("received_at") or time.time(), d["contact_id"]))
        return cur.rowcount > 0


def _inbox_where(box="", q=""):
    where, args = ["i.archived=0"], []
    if box in ("", "replies"):
        where.append("i.kind='reply'")
    elif box == "unread":
        where.append("i.kind='reply' AND i.is_read=0")
    elif box in ("interested", "not_interested", "meeting", "unsubscribe"):
        where.append("i.label=?")
        args.append(box)
    elif box == "auto":
        where.append("i.kind='auto'")
    elif box == "bounces":
        where.append("i.kind IN ('bounce','complaint')")
    elif box == "archived":
        where = ["i.archived=1"]
    elif box == "all":
        pass
    if q:
        where.append("(i.from_email LIKE ? OR i.subject LIKE ? OR i.snippet LIKE ?)")
        args += [f"%{q}%"] * 3
    return " AND ".join(where), args


def inbox_list(box="", q="", page=0, per=40):
    w, args = _inbox_where(box, q)
    with _LOCK, _conn() as c:
        total = c.execute(f"SELECT COUNT(*) FROM inbox i WHERE {w}", args).fetchone()[0]
        rows = [dict(r) for r in c.execute(
            f"SELECT i.id,i.kind,i.from_email,i.from_name,i.subject,i.snippet,i.received_at,"
            f"i.is_read,i.label,i.campaign_id,i.contact_id,i.account_id,cp.name campaign "
            f"FROM inbox i LEFT JOIN campaigns cp ON cp.id=i.campaign_id WHERE {w} "
            f"ORDER BY i.received_at DESC LIMIT ? OFFSET ?", args + [per, page * per])]
    return {"total": total, "rows": rows, "page": page, "per": per}


def inbox_get(iid, mark_read=True):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT i.*, cp.name campaign, a.from_email account_email FROM inbox i "
                      "LEFT JOIN campaigns cp ON cp.id=i.campaign_id "
                      "LEFT JOIN accounts a ON a.id=i.account_id WHERE i.id=?", (iid,)).fetchone()
        if r and mark_read and not r["is_read"]:
            c.execute("UPDATE inbox SET is_read=1 WHERE id=?", (iid,))
    return dict(r) if r else None


def inbox_update(iid, **kw):
    kw = {k: v for k, v in kw.items() if k in ("label", "is_read", "archived")}
    if kw:
        with _LOCK, _conn() as c:
            c.execute(f"UPDATE inbox SET {','.join(k + '=?' for k in kw)} WHERE id=?",
                      list(kw.values()) + [iid])


def inbox_mark_all_read():
    with _LOCK, _conn() as c:
        c.execute("UPDATE inbox SET is_read=1 WHERE is_read=0")


def inbox_counts():
    with _LOCK, _conn() as c:
        def n(q, *a):
            return c.execute(q, a).fetchone()[0]
        return {
            "unread": n("SELECT COUNT(*) FROM inbox WHERE kind='reply' AND is_read=0 AND archived=0"),
            "replies": n("SELECT COUNT(*) FROM inbox WHERE kind='reply' AND archived=0"),
            "interested": n("SELECT COUNT(*) FROM inbox WHERE label='interested' AND archived=0"),
            "not_interested": n("SELECT COUNT(*) FROM inbox WHERE label='not_interested' AND archived=0"),
            "meeting": n("SELECT COUNT(*) FROM inbox WHERE label='meeting' AND archived=0"),
            "unsubscribe": n("SELECT COUNT(*) FROM inbox WHERE label='unsubscribe' AND archived=0"),
            "auto": n("SELECT COUNT(*) FROM inbox WHERE kind='auto' AND archived=0"),
            "bounces": n("SELECT COUNT(*) FROM inbox WHERE kind IN ('bounce','complaint') AND archived=0"),
            "archived": n("SELECT COUNT(*) FROM inbox WHERE archived=1"),
        }


def inbox_thread(contact_id, limit=30):
    if not contact_id:
        return []
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT id,kind,from_email,from_name,subject,body,snippet,received_at FROM inbox "
            "WHERE contact_id=? AND kind IN ('reply','auto','outgoing') "
            "ORDER BY received_at ASC LIMIT ?", (contact_id, limit))]


def replied_since(ts):
    with _LOCK, _conn() as c:
        return {r[0] for r in c.execute("SELECT id FROM contacts WHERE replied_at>=?", (ts,))}


def repliers_of_sequence(parent_id):
    """Contacts who replied to a campaign or any of its follow-ups (or since it started)."""
    with _LOCK, _conn() as c:
        p = c.execute("SELECT created_at FROM campaigns WHERE id=?", (parent_id,)).fetchone()
        ids = [parent_id] + [r[0] for r in c.execute("SELECT id FROM campaigns WHERE parent_id=?",
                                                     (parent_id,))]
        q = ",".join("?" * len(ids))
        out = {r[0] for r in c.execute(f"SELECT DISTINCT contact_id FROM inbox WHERE kind='reply' "
                                       f"AND campaign_id IN ({q})", ids)}
        if p:
            out |= {r[0] for r in c.execute("SELECT id FROM contacts WHERE replied_at>=?",
                                            (p["created_at"],))}
    return out


# --------------------------- campaigns + events ----------------------------- #
def create_campaign(d):
    with _LOCK, _conn() as c:
        return c.execute(
            "INSERT INTO campaigns(name,subject,subject_b,html,text,list_id,account_ids,"
            "track_opens,track_clicks,rate,jitter,parent_id,step_no,send_to,scheduled_at,"
            "status,created_at,group_ids,exclude_group_ids,brakes) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (d.get("name", "Campaign"), d.get("subject", ""), d.get("subject_b", ""),
             d.get("html", ""), d.get("text", ""), d.get("list_id") or None,
             json.dumps(d.get("account_ids") or []), int(d.get("track_opens", 1)),
             int(d.get("track_clicks", 1)), int(d.get("rate", 60)), float(d.get("jitter", 2)),
             int(d.get("parent_id", 0)), int(d.get("step_no", 0)), d.get("send_to", "all"),
             float(d.get("scheduled_at") or 0), d.get("status", "draft"), time.time(),
             json.dumps(d.get("group_ids") or []), json.dumps(d.get("exclude_group_ids") or []),
             int(d.get("brakes", 1)))).lastrowid


def campaign_groups(camp):
    """(group_ids, exclude_group_ids) for a campaign row, incl. legacy list_id."""
    def parse(v):
        try:
            return [int(x) for x in json.loads(v or "[]")]
        except Exception:
            return []
    g = parse(camp.get("group_ids"))
    if not g and camp.get("list_id"):
        g = [int(camp["list_id"])]
    return g, parse(camp.get("exclude_group_ids"))


def log_send(cid, contact_id, email, status, variant="A", error="", message_id="", account_id=0):
    with _LOCK, _conn() as c:
        c.execute("INSERT INTO sends(campaign_id,contact_id,email,status,variant,error,sent_at,"
                  "message_id,account_id) VALUES(?,?,?,?,?,?,?,?,?)",
                  (cid, contact_id, email, status, variant, error, time.time(), message_id,
                   account_id))


def log_event(cid, contact_id, type_, url=""):
    with _LOCK, _conn() as c:
        if type_ == "unsub":
            if c.execute("SELECT 1 FROM events WHERE campaign_id=? AND contact_id=? AND type='unsub'",
                         (cid, contact_id)).fetchone():
                return
        c.execute("INSERT INTO events(campaign_id,contact_id,type,url,ts) VALUES(?,?,?,?,?)",
                  (cid, contact_id, type_, url, time.time()))


def update_campaign_counts(cid, sent, failed, skipped, status=None):
    with _LOCK, _conn() as c:
        if status:
            c.execute("UPDATE campaigns SET sent=?,failed=?,skipped=?,status=? WHERE id=?",
                      (sent, failed, skipped, status, cid))
        else:
            c.execute("UPDATE campaigns SET sent=?,failed=?,skipped=? WHERE id=?",
                      (sent, failed, skipped, cid))


def set_campaign_status(cid, status):
    with _LOCK, _conn() as c:
        c.execute("UPDATE campaigns SET status=? WHERE id=?", (status, cid))


def set_campaign_field(cid, **kw):
    with _LOCK, _conn() as c:
        c.execute(f"UPDATE campaigns SET {','.join(k + '=?' for k in kw)} WHERE id=?",
                  list(kw.values()) + [cid])


def delete_campaign(cid):
    with _LOCK, _conn() as c:
        kids = [r[0] for r in c.execute("SELECT id FROM campaigns WHERE parent_id=?", (cid,))]
        for x in kids + [cid]:
            c.execute("DELETE FROM campaigns WHERE id=?", (x,))


def due_campaigns():
    with _LOCK, _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM campaigns WHERE (status='scheduled' AND scheduled_at>0 AND scheduled_at<=?)"
            " OR status='queued' ORDER BY scheduled_at, id", (time.time(),))]


def get_campaign(cid):
    with _LOCK, _conn() as c:
        r = c.execute("SELECT * FROM campaigns WHERE id=?", (cid,)).fetchone()
        return dict(r) if r else None


def send_counts(cid):
    with _LOCK, _conn() as c:
        by = {r[0]: r[1] for r in c.execute(
            "SELECT status,COUNT(*) FROM sends WHERE campaign_id=? GROUP BY status", (cid,))}
    return by


def logged_contacts_of(cid):
    with _LOCK, _conn() as c:
        return {r[0] for r in c.execute(
            "SELECT DISTINCT contact_id FROM sends WHERE campaign_id=? AND status!='failed'", (cid,))}


def sent_contacts_of(cid):
    with _LOCK, _conn() as c:
        return {r[0] for r in c.execute(
            "SELECT DISTINCT contact_id FROM sends WHERE campaign_id=? AND status='sent'", (cid,))}


def openers_of(cid):
    with _LOCK, _conn() as c:
        return {r[0] for r in c.execute(
            "SELECT DISTINCT contact_id FROM events WHERE campaign_id=? AND type='open'", (cid,))}


def _event_counts(c, cid):
    o = c.execute("SELECT COUNT(DISTINCT contact_id) FROM events WHERE campaign_id=? "
                  "AND type='open'", (cid,)).fetchone()[0]
    cl = c.execute("SELECT COUNT(DISTINCT contact_id) FROM events WHERE campaign_id=? "
                   "AND type='click'", (cid,)).fetchone()[0]
    rp = c.execute("SELECT COUNT(DISTINCT contact_id) FROM inbox WHERE campaign_id=? "
                   "AND kind='reply'", (cid,)).fetchone()[0]
    return {"opens": o, "clicks": cl, "replies": rp}


def campaigns(parent_only=False):
    with _LOCK, _conn() as c:
        q = ("SELECT id,name,subject,status,sent,failed,skipped,bounced,scheduled_at,parent_id,"
             "step_no,created_at,brake_reason,group_ids,list_id,tracking FROM campaigns")
        if parent_only:
            q += " WHERE parent_id=0"
        rows = [dict(r) for r in c.execute(q + " ORDER BY created_at DESC LIMIT 300")]
        for r in rows:
            r.update(_event_counts(c, r["id"]))
    return rows


def campaign_report(cid):
    with _LOCK, _conn() as c:
        camp = c.execute("SELECT * FROM campaigns WHERE id=?", (cid,)).fetchone()
        if not camp:
            return {}
        by = {r["status"]: r["n"] for r in c.execute(
            "SELECT status,COUNT(*) n FROM sends WHERE campaign_id=? GROUP BY status", (cid,))}
        fails = [dict(f) for f in c.execute(
            "SELECT email,error,status FROM sends WHERE campaign_id=? AND status IN "
            "('failed','bounced') ORDER BY sent_at DESC LIMIT 200", (cid,))]
        links = [dict(r) for r in c.execute(
            "SELECT url, COUNT(*) n FROM events WHERE campaign_id=? AND type='click' AND url!='' "
            "GROUP BY url ORDER BY n DESC LIMIT 10", (cid,))]
        variants = {}
        for r in c.execute("SELECT variant, COUNT(*) n FROM sends WHERE campaign_id=? "
                           "AND status='sent' GROUP BY variant", (cid,)):
            variants.setdefault(r["variant"], {})["sent"] = r["n"]
        for r in c.execute(
            "SELECT s.variant v, COUNT(DISTINCT e.contact_id) n FROM events e "
            "JOIN sends s ON s.contact_id=e.contact_id AND s.campaign_id=e.campaign_id "
                "WHERE e.campaign_id=? AND e.type='open' GROUP BY s.variant", (cid,)):
            variants.setdefault(r["v"], {})["opens"] = r["n"]
        activity = [dict(r) for r in c.execute(
            "SELECT e.type,e.url,e.ts,c.email FROM events e LEFT JOIN contacts c ON c.id=e.contact_id "
            "WHERE e.campaign_id=? ORDER BY e.ts DESC LIMIT 40", (cid,))]
        replies = [dict(r) for r in c.execute(
            "SELECT id,from_email,from_name,subject,snippet,received_at,label,kind FROM inbox "
            "WHERE campaign_id=? AND kind IN ('reply','auto') ORDER BY received_at DESC LIMIT 30",
            (cid,))]
        children = [dict(r) for r in c.execute(
            "SELECT id,name,status,sent,scheduled_at,step_no,send_to FROM campaigns WHERE parent_id=? "
            "ORDER BY step_no", (cid,))]
        ev = _event_counts(c, cid)
    health = campaign_health(cid)
    g, ex = campaign_groups(dict(camp))
    gnames = {x["id"]: x for x in groups()}
    return {"campaign": dict(camp), "by_status": by, "failures": fails, "links": links,
            "variants": variants, "activity": activity, "children": children, "replies": replies,
            "health": health, "groups": [gnames[i] for i in g if i in gnames],
            "excluded": [gnames[i] for i in ex if i in gnames], **ev}


def campaign_report_csv(cid):
    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["email", "status", "variant", "opened", "clicked", "replied", "error"])
    with _LOCK, _conn() as c:
        opens = {r[0] for r in c.execute("SELECT DISTINCT contact_id FROM events WHERE "
                                         "campaign_id=? AND type='open'", (cid,))}
        clicks = {r[0] for r in c.execute("SELECT DISTINCT contact_id FROM events WHERE "
                                          "campaign_id=? AND type='click'", (cid,))}
        reps = {r[0] for r in c.execute("SELECT DISTINCT contact_id FROM inbox WHERE "
                                        "campaign_id=? AND kind='reply'", (cid,))}
        for r in c.execute("SELECT contact_id,email,status,variant,error FROM sends "
                           "WHERE campaign_id=?", (cid,)):
            w.writerow([r["email"], r["status"], r["variant"],
                        "yes" if r["contact_id"] in opens else "",
                        "yes" if r["contact_id"] in clicks else "",
                        "yes" if r["contact_id"] in reps else "", r["error"] or ""])
    return out.getvalue()


def dashboard():
    with _LOCK, _conn() as c:
        camps = c.execute("SELECT COUNT(*) FROM campaigns WHERE parent_id=0").fetchone()[0]
        total_sent = c.execute("SELECT COUNT(*) FROM sends WHERE status='sent'").fetchone()[0]
        opens = c.execute("SELECT COUNT(DISTINCT campaign_id||'-'||contact_id) FROM events "
                          "WHERE type='open'").fetchone()[0]
        clicks = c.execute("SELECT COUNT(DISTINCT campaign_id||'-'||contact_id) FROM events "
                           "WHERE type='click'").fetchone()[0]
        replies = c.execute("SELECT COUNT(*) FROM inbox WHERE kind='reply'").fetchone()[0]
        hard = c.execute("SELECT COUNT(*) FROM bounces WHERE kind='hard'").fetchone()[0]
        recent = [dict(r) for r in c.execute(
            "SELECT id,name,status,sent,failed,bounced,created_at FROM campaigns WHERE parent_id=0 "
            "ORDER BY created_at DESC LIMIT 6")]
        for r in recent:
            r.update(_event_counts(c, r["id"]))
        since = time.time() - 14 * 86400
        series = {}
        for r in c.execute("SELECT date(sent_at,'unixepoch','localtime') d, COUNT(*) n FROM sends "
                           "WHERE status='sent' AND sent_at>? GROUP BY d", (since,)):
            series.setdefault(r["d"], {})["sent"] = r["n"]
        for r in c.execute("SELECT date(ts,'unixepoch','localtime') d, COUNT(DISTINCT "
                           "campaign_id||'-'||contact_id) n FROM events WHERE type='open' AND ts>? "
                           "GROUP BY d", (since,)):
            series.setdefault(r["d"], {})["opens"] = r["n"]
        for r in c.execute("SELECT date(received_at,'unixepoch','localtime') d, COUNT(*) n FROM "
                           "inbox WHERE kind='reply' AND received_at>? GROUP BY d", (since,)):
            series.setdefault(r["d"], {})["replies"] = r["n"]
        latest_replies = [dict(r) for r in c.execute(
            "SELECT id,from_email,from_name,subject,snippet,received_at,label,is_read FROM inbox "
            "WHERE kind='reply' AND archived=0 ORDER BY received_at DESC LIMIT 5")]
    days = []
    for i in range(13, -1, -1):
        d = (_dt.date.today() - _dt.timedelta(days=i)).isoformat()
        s = series.get(d, {})
        days.append({"d": d, "sent": s.get("sent", 0), "opens": s.get("opens", 0),
                     "replies": s.get("replies", 0)})

    def pct(n):
        return round(n / total_sent * 100, 1) if total_sent else 0
    return {"campaigns": camps, "total_sent": total_sent, "opens": opens, "clicks": clicks,
            "replies": replies, "hard_bounces": hard,
            "open_rate": pct(opens), "click_rate": pct(clicks), "reply_rate": pct(replies),
            "bounce_rate": round(hard / (total_sent + hard) * 100, 2) if total_sent + hard else 0,
            "contacts": contact_stats(), "recent": recent, "series": days,
            "latest_replies": latest_replies}
