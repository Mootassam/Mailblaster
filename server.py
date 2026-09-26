#!/usr/bin/env python3
"""
MailBlaster — a local cold-email & campaign platform (private Mailchimp/Brevo).

Concurrent campaigns, per-campaign senders + contact groups, A/B subjects,
follow-up sequences, open/click tracking, IMAP bounce + reply processing with a
unified inbox, sender warm-up, automatic safety brakes, list validation, spam
scoring, scheduling, crash-safe resume and a domain-health checker.

    python server.py   ->   http://127.0.0.1:5055
"""

from __future__ import annotations

import collections
import csv
import html as _html
import io
import json
import os
import random
import sys
import threading
import time

from flask import Flask, Response, abort, jsonify, redirect, request, send_from_directory

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import store  # noqa: E402
import mailer  # noqa: E402
import inbox_sync  # noqa: E402
import tunnel  # noqa: E402
from templates_data import TEMPLATES  # noqa: E402

try:
    import app_paths
    _STATIC = app_paths.static_dir()
    store.set_db_path(os.path.join(app_paths.data_dir(), "mailblaster.db"))
except Exception:  # running from source without the helper
    app_paths = None
    _STATIC = os.path.join(HERE, "static")
if os.environ.get("MB_DB"):          # alternate database (testing / multiple workspaces)
    store.set_db_path(os.environ["MB_DB"])

app = Flask(__name__, static_folder=_STATIC)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024
store.init()

_PIXEL = (b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04"
          b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")

# ---- concurrent campaign jobs, keyed by campaign id ---- #
JOBS: dict[int, dict] = {}
_JOBS_LOCK = threading.Lock()
MAX_CONCURRENT = 6
SENDER_MAX_CONSEC = 5          # a sender is auto-paused after this many failures in a row


def _s(name, default=""):
    return (request.form.get(name) or default).strip()


def _ids(name):
    """Ints from repeated form fields and/or a comma-separated value."""
    out = []
    for v in request.form.getlist(name) + request.args.getlist(name):
        for x in str(v).split(","):
            x = x.strip()
            if x.isdigit():
                out.append(int(x))
    return list(dict.fromkeys(out))


LOCAL_URL = "http://127.0.0.1:5055"  # updated at startup; used when off the request thread


def _base_url():
    st = store.get_settings()
    if st.get("track_base"):
        return st["track_base"].rstrip("/")
    try:
        from flask import has_request_context
        if has_request_context():
            return request.host_url.rstrip("/")
    except Exception:
        pass
    return LOCAL_URL


def _tracking_mode():
    """'full'  = own permanent public URL: pixel + click tracking + web unsubscribe
    'opens' = automatic Cloudflare tunnel (address changes on restart): pixel only;
              links and unsubscribe never depend on this PC being reachable
    'none'  = no public address: links untouched, nothing tracked"""
    st = store.get_settings()
    if st.get("track_mode") == "auto":
        t = tunnel.status()
        return ("opens", t["url"]) if t["status"] == "on" and t["url"] else ("none", "")
    b = _public_base(st)
    return ("full", b) if b else ("none", "")


def _public_base(st=None):
    """The custom tracking URL recipients can actually reach, or "" when none is set.
    127.0.0.1 / localhost only exist on this PC — links there are dead for recipients."""
    st = st or store.get_settings()
    if st.get("track_mode") == "auto":
        return ""
    b = (st.get("track_base") or "").strip().rstrip("/")
    if not b.startswith(("http://", "https://")):
        return ""
    host = b.split("://", 1)[1].split("/", 1)[0].split(":", 1)[0].lower()
    if host in ("127.0.0.1", "localhost", "0.0.0.0", "::1") or host.startswith(("192.168.", "10.")):
        return ""
    return b


def _running_count():
    with _JOBS_LOCK:
        return sum(1 for j in JOBS.values() if j["status"] == "running")


def _is_running(cid):
    with _JOBS_LOCK:
        return JOBS.get(cid, {}).get("status") == "running"


# ------------------------------ public-access guard ------------------------- #
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}
_PUBLIC_PREFIXES = ("/t/o/", "/t/c/", "/u/")
_PROXY_HEADERS = ("Cf-Connecting-Ip", "Cf-Ray", "X-Forwarded-For", "X-Forwarded-Host",
                  "X-Real-Ip", "Forwarded", "Ngrok-Trace-Id")


def _is_local_request():
    host = (request.host or "").rsplit(":", 1)[0].lower() if not (request.host or "").startswith("[") \
        else (request.host or "").split("]")[0] + "]"
    if host not in _LOCAL_HOSTS or request.remote_addr not in ("127.0.0.1", "::1"):
        return False
    return not any(request.headers.get(h) for h in _PROXY_HEADERS)


@app.before_request
def _guard_public_access():
    """Anything arriving through a tunnel / public URL may only reach the tracking pixel,
    tracked-link redirects and the unsubscribe page — never the app or its API."""
    if _is_local_request():
        return None
    if request.path.startswith(_PUBLIC_PREFIXES):
        return None
    return Response("Not found", status=404, mimetype="text/plain")


# ------------------------------ static + state ------------------------------ #
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/state")
def api_state():
    st = store.get_settings()
    with _JOBS_LOCK:
        jobs = {cid: dict(j) for cid, j in JOBS.items()}
    with _IMAP_LOCK:
        imap = dict(IMAP)
    return jsonify({
        "contacts": store.contact_stats(), "groups": store.groups(), "accounts": store.accounts(),
        "settings": st, "presets": mailer.PRESETS,
        "imap_presets": {k: {"host": v[0], "port": v[1], "security": v[2]}
                         for k, v in inbox_sync.IMAP_PRESETS.items()},
        "campaigns": store.campaigns(parent_only=True),
        "templates": [{"id": t["id"], "name": t["name"], "category": t["category"]} for t in TEMPLATES],
        "jobs": jobs, "inbox": store.inbox_counts(), "imap": imap,
        "tunnel": tunnel.status(), "tracking": _tracking_mode()[0],
    })


@app.route("/api/dashboard")
def api_dashboard():
    return jsonify(store.dashboard())


@app.route("/api/templates/<tid>")
def api_template(tid):
    t = next((x for x in TEMPLATES if x["id"] == tid), None)
    return jsonify(t or {}), (200 if t else 404)


@app.route("/api/settings", methods=["POST"])
def api_settings():
    d = {}
    for k in store.DEFAULT_SETTINGS:
        if k in request.form and k != "track_mode":
            d[k] = request.form.get(k, "").strip()
    if "track_base" in d:
        d["track_mode"] = "custom" if d["track_base"] else ""
        tunnel.stop()
    store.save_settings(d)
    return jsonify({"ok": True})


# ------------------------------ public tracking tunnel ---------------------- #
def _tunnel_url(url):
    store.save_settings({"track_mode": "auto", "track_base": url})


@app.route("/api/tunnel/start", methods=["POST"])
def api_tunnel_start():
    store.save_settings({"track_mode": "auto", "track_base": ""})
    tunnel.start(_port(), _tunnel_url)
    return jsonify({"ok": True, **tunnel.status()})


@app.route("/api/tunnel/stop", methods=["POST"])
def api_tunnel_stop():
    tunnel.stop()
    store.save_settings({"track_mode": "", "track_base": ""})
    return jsonify({"ok": True, **tunnel.status()})


@app.route("/api/tunnel/status")
def api_tunnel_status():
    return jsonify({**tunnel.status(), "mode": _tracking_mode()[0],
                    "track_mode": store.get_settings().get("track_mode", "")})


def _port():
    try:
        return int(LOCAL_URL.rsplit(":", 1)[1])
    except Exception:
        return 5055


# ------------------------------ suggestions --------------------------------- #
_SUBJECT_IDEAS = [
    "Quick question, {{first_name|there}}",
    "{{first_name|Hi}} — idea for {{data.company|your team}}",
    "Worth a quick chat?",
    "Should I stay or should I go?",
    "{{data.company|Your team}} + [your solution]",
    "A 15% idea for {{data.company|you}}",
    "Re: growing {{data.company|your business}}",
    "Mind if I send a quick example?",
    "{{first_name|there}}, saw this and thought of you",
    "Last try, {{first_name|there}}",
]


@app.route("/api/suggest/subjects")
def api_suggest():
    ideas = random.sample(_SUBJECT_IDEAS, min(6, len(_SUBJECT_IDEAS)))
    tips = ["Keep it under ~50 characters so it isn't cut off on mobile.",
            "Personalize with {{first_name}} — it lifts open rates.",
            "Avoid ALL CAPS, 'FREE', and lots of '!!!' — they trigger spam filters.",
            "Best cold-email send times are Tue–Thu, 8–10am in the recipient's timezone."]
    return jsonify({"subjects": ideas, "tips": tips})


# ------------------------------ domain health ------------------------------- #
@app.route("/api/domain-check")
def api_domain_check():
    domain = (request.args.get("domain") or "").strip().lower()
    domain = domain.split("@")[-1].strip("/ ")
    if "." not in domain:
        return jsonify({"ok": False, "error": "Enter a domain like yourdomain.com"}), 400
    out = {"ok": True, "domain": domain, "spf": None, "dmarc": None, "mx": None,
           "spf_record": "", "dmarc_record": "", "dmarc_policy": ""}
    try:
        import dns.resolver
        r = dns.resolver.Resolver()
        r.lifetime = r.timeout = 5
        try:
            out["mx"] = len(r.resolve(domain, "MX")) > 0
        except Exception:
            out["mx"] = False
        try:
            txt = [b"".join(x.strings).decode("utf-8", "ignore") for x in r.resolve(domain, "TXT")]
            spf = [t for t in txt if t.lower().startswith("v=spf1")]
            out["spf"] = bool(spf)
            out["spf_record"] = spf[0] if spf else ""
        except Exception:
            out["spf"] = False
        try:
            dtxt = [b"".join(x.strings).decode("utf-8", "ignore")
                    for x in r.resolve("_dmarc." + domain, "TXT")]
            dm = [t for t in dtxt if "v=dmarc1" in t.lower()]
            out["dmarc"] = bool(dm)
            out["dmarc_record"] = dm[0] if dm else ""
            if dm:
                import re as _re
                m = _re.search(r"\bp=(\w+)", dm[0], _re.I)
                out["dmarc_policy"] = m.group(1).lower() if m else ""
        except Exception:
            out["dmarc"] = False
    except Exception as e:
        return jsonify({"ok": False, "error": f"DNS lookup failed ({e})."}), 400
    return jsonify(out)


# ------------------------------ sender accounts ----------------------------- #
_ACC_FORM = ["label", "host", "port", "security", "username", "password", "from_name",
             "from_email", "reply_to", "daily_limit", "active", "imap_enabled", "imap_host",
             "imap_port", "imap_security", "imap_user", "imap_password", "imap_folders",
             "warmup_enabled", "warmup_start", "warmup_growth"]


def _acc_form():
    return {k: request.form.get(k, "").strip() for k in _ACC_FORM if k in request.form}


@app.route("/api/accounts", methods=["POST"])
def api_add_account():
    d = _acc_form()
    if not d.get("host") or not d.get("from_email"):
        return jsonify({"ok": False, "error": "SMTP host and From email are required."}), 400
    return jsonify({"ok": True, "id": store.add_account(d)})


@app.route("/api/accounts/<int:aid>", methods=["POST"])
def api_update_account(aid):
    if _s("_delete") == "1":
        store.delete_account(aid)
        return jsonify({"ok": True})
    store.update_account(aid, _acc_form())
    return jsonify({"ok": True})


@app.route("/api/accounts/<int:aid>/test", methods=["POST"])
def api_test_account(aid):
    a = store.get_account(aid)
    if not a:
        abort(404)
    try:
        mailer.SMTPSender(a["host"], a["port"], a["security"], a["username"], a["password"]).verify()
        return jsonify({"ok": True, "message": "SMTP connected & signed in."})
    except mailer.MailerError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed ({e})."}), 400


@app.route("/api/imap/test", methods=["POST"])
def api_imap_test():
    """Test IMAP with the (unsaved) form values, falling back to the stored account."""
    aid = int(_s("id", "0") or 0)
    acc = (store.get_account(aid) if aid else None) or {}
    for k, v in _acc_form().items():
        if k in ("password", "imap_password") and not v:
            continue
        acc[k] = v
    try:
        n = inbox_sync.test(acc)
        host = inbox_sync.imap_settings(acc)[0]
        return jsonify({"ok": True, "message": f"IMAP connected to {host} — {n} messages in INBOX."})
    except inbox_sync.SyncError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed ({e})."}), 400


@app.route("/api/accounts/<int:aid>/warmup-restart", methods=["POST"])
def api_warmup_restart(aid):
    store.restart_warmup(aid)
    return jsonify({"ok": True})


@app.route("/api/accounts/<int:aid>/unpause", methods=["POST"])
def api_unpause(aid):
    store.set_account_fields(aid, paused_reason="")
    return jsonify({"ok": True})


@app.route("/api/accounts/<int:aid>/sync", methods=["POST"])
def api_sync_account(aid):
    threading.Thread(target=_sync_one, args=(aid, True), daemon=True).start()
    return jsonify({"ok": True})


# ------------------------------ groups -------------------------------------- #
@app.route("/api/groups")
def api_groups():
    return jsonify(store.groups())


@app.route("/api/groups", methods=["POST"])
def api_group_create():
    name = _s("name")
    if not name:
        return jsonify({"ok": False, "error": "Give the group a name."}), 400
    return jsonify({"ok": True, "id": store.create_group(name, _s("color"))})


@app.route("/api/groups/<int:gid>", methods=["POST"])
def api_group_update(gid):
    try:
        store.update_group(gid, _s("name") or None, _s("color") or None)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True})


@app.route("/api/groups/<int:gid>/delete", methods=["POST"])
def api_group_delete(gid):
    n = store.delete_group(gid, delete_contacts=_s("delete_contacts") == "1")
    return jsonify({"ok": True, "deleted_contacts": n})


@app.route("/api/recipients/count")
def api_recipient_count():
    return jsonify({"count": store.recipient_count(_ids("groups"), _ids("exclude"))})


# ------------------------------ contacts ------------------------------------ #
def _guess(headers, *names):
    low = {h.lower().strip(): h for h in headers}
    for n in names:
        if n in low:
            return low[n]
    for h in headers:
        if any(n in h.lower() for n in names):
            return h
    return None


@app.route("/api/contacts/import", methods=["POST"])
def api_import():
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "Choose a CSV file."}), 400
    raw = f.read()
    text = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except Exception:
            continue
    text = text or raw.decode("utf-8", "replace")
    try:
        dialect = csv.Sniffer().sniff(text[:20000], delimiters=",;\t|")
    except Exception:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    headers = [h for h in (reader.fieldnames or []) if h]
    if not headers:
        return jsonify({"ok": False, "error": "That CSV has no header row."}), 400
    email_col = _s("email_col") or _guess(headers, "email", "e-mail", "mail")
    fn = _s("first_col") or _guess(headers, "first_name", "first name", "firstname", "first",
                                   "fname", "given", "name")
    ln = _s("last_col") or _guess(headers, "last_name", "last name", "lastname", "last", "lname",
                                  "surname")
    if not email_col:
        return jsonify({"ok": False, "error": "No email column found (name one 'email').",
                        "headers": headers}), 400
    rows = []
    for row in reader:
        rec = {"email": row.get(email_col, ""), "first_name": row.get(fn, "") if fn else "",
               "last_name": row.get(ln, "") if ln else ""}
        for h in headers:
            if h not in (email_col, fn, ln):
                rec[h] = row.get(h, "")
        rows.append(rec)
    gid = _s("group_id")
    if gid.isdigit():
        group_id = int(gid)
    elif _s("list_name") or _s("group_name"):
        group_id = store.create_group(_s("group_name") or _s("list_name"))
    else:
        group_id = None
    res = store.import_contacts(rows, group_id)
    res.update(ok=True, group_id=group_id, rows=len(rows))
    return jsonify(res)


def _filt_args(src):
    return {"q": src.get("q", ""), "status": src.get("status", ""), "group": src.get("group", "")}


@app.route("/api/contacts/list")
def api_contacts_list():
    a = request.args
    return jsonify(store.search_contacts(a.get("q", ""), a.get("status", ""),
                                         int(a.get("page", 0) or 0), int(a.get("per", 50) or 50),
                                         a.get("group", "")))


@app.route("/api/contacts/<int:cid>")
def api_contact_detail(cid):
    d = store.contact_detail(cid)
    return (jsonify(d), 200) if d else (jsonify({}), 404)


@app.route("/api/contacts/add", methods=["POST"])
def api_contact_add():
    email = _s("email")
    gid = _ids("group_ids")
    cid = store.add_contact(email, _s("first_name"), _s("last_name"), {}, gid[0] if gid else None)
    if cid:
        for g in gid[1:]:
            store.bulk_contacts("add_group", ids=[cid], group_id=g)
    return jsonify({"ok": True, "id": cid} if cid else {"ok": False, "error": "Invalid email."})


@app.route("/api/contacts/<int:cid>/delete", methods=["POST"])
def api_contact_delete(cid):
    store.delete_contact(cid)
    return jsonify({"ok": True})


@app.route("/api/contacts/bulk", methods=["POST"])
def api_contacts_bulk():
    action = _s("action")
    if action not in ("delete", "add_group", "remove_group", "unsubscribe", "reactivate"):
        return jsonify({"ok": False, "error": "Unknown action."}), 400
    group_id = int(_s("group_id", "0") or 0) or None
    if action == "add_group" and _s("new_group"):
        group_id = store.create_group(_s("new_group"))
    if action in ("add_group", "remove_group") and not group_id:
        return jsonify({"ok": False, "error": "Pick a group."}), 400
    if _s("all") == "1":
        n = store.bulk_contacts(action, filt=_filt_args(request.form), group_id=group_id)
    else:
        ids = _ids("ids")
        if not ids:
            return jsonify({"ok": False, "error": "Select at least one contact."}), 400
        n = store.bulk_contacts(action, ids=ids, group_id=group_id)
    return jsonify({"ok": True, "count": n, "group_id": group_id})


@app.route("/api/contacts/delete-all", methods=["POST"])
def api_contacts_delete_all():
    if _s("confirm") != "DELETE":
        return jsonify({"ok": False, "error": "Type DELETE to confirm."}), 400
    return jsonify({"ok": True, "count": store.delete_all_contacts()})


@app.route("/api/unsubscribe", methods=["POST"])
def api_unsub():
    return jsonify({"ok": store.unsubscribe(_s("email"), "manual")})


# ---- validation job ---- #
VALIDATE = {"status": "idle", "total": 0, "done": 0, "invalid": 0}
_VLOCK = threading.Lock()


def _run_validate(check_mx):
    emails = store.all_active_emails()
    with _VLOCK:
        VALIDATE.update(status="running", total=len(emails), done=0, invalid=0)
    inv = 0
    for cid, email in emails:
        ok, why = mailer.validate_email(email, check_mx=check_mx)
        if not ok:
            store.set_status(cid, "invalid", why)
            inv += 1
        with _VLOCK:
            VALIDATE["done"] += 1
            VALIDATE["invalid"] = inv
    with _VLOCK:
        VALIDATE["status"] = "done"


@app.route("/api/validate", methods=["POST"])
def api_validate():
    with _VLOCK:
        if VALIDATE["status"] == "running":
            return jsonify({"ok": False, "error": "Already running."}), 400
    threading.Thread(target=_run_validate, args=(_s("check_mx", "1") == "1",), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/validate/status")
def api_validate_status():
    with _VLOCK:
        return jsonify(dict(VALIDATE))


@app.route("/api/spam-check", methods=["POST"])
def api_spam():
    return jsonify(mailer.spam_check(_s("subject"), _s("html")))


# ------------------------------ deliverability ------------------------------ #
@app.route("/api/deliverability")
def api_deliverability():
    return jsonify({"stats": store.deliverability_stats(int(request.args.get("days", 30) or 30)),
                    "bounces": store.recent_bounces(100, request.args.get("q", "")),
                    "accounts": store.accounts(), "settings": store.get_settings()})


@app.route("/api/suppression")
def api_suppression():
    return jsonify(store.suppression_list(request.args.get("q", ""),
                                          int(request.args.get("page", 0) or 0)))


@app.route("/api/suppression/add", methods=["POST"])
def api_suppression_add():
    raw = _s("emails")
    emails = [e for e in raw.replace(";", "\n").replace(",", "\n").split() if e]
    return jsonify({"ok": True, "count": store.suppression_add(emails, "manual")})


@app.route("/api/suppression/remove", methods=["POST"])
def api_suppression_remove():
    store.suppression_remove([_s("email")])
    return jsonify({"ok": True})


@app.route("/api/export/suppression.csv")
def export_suppression():
    return Response(store.suppression_csv(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=suppression.csv"})


# ------------------------------ inbox --------------------------------------- #
IMAP = {"running": False, "last_run": 0, "last_result": {}, "current": ""}
_IMAP_LOCK = threading.Lock()
_SYNC_LOCK = threading.Lock()


def _sync_one(aid, force=False):
    acc = store.get_account(aid)
    if not acc or (not acc.get("imap_enabled") and not force):
        return None
    with _IMAP_LOCK:
        IMAP["current"] = acc.get("from_email", "")
    try:
        res = inbox_sync.sync_account(acc)
        store.set_account_fields(aid, imap_last_check=time.time(), imap_error="")
        return res
    except inbox_sync.SyncError as e:
        store.set_account_fields(aid, imap_last_check=time.time(), imap_error=str(e)[:300])
    except Exception as e:
        store.set_account_fields(aid, imap_last_check=time.time(),
                                 imap_error=f"{type(e).__name__}: {e}"[:300])
    return None


def _sync_all(force=False):
    if not _SYNC_LOCK.acquire(blocking=False):
        return
    try:
        with _IMAP_LOCK:
            IMAP.update(running=True)
        st = store.get_settings()
        every = max(1.0, store.setting_num(st, "imap_interval_min", 5)) * 60
        total = collections.Counter()
        for a in store.accounts(hide_pw=True):
            if not a.get("imap_enabled"):
                continue
            if not force and time.time() - (a.get("imap_last_check") or 0) < every:
                continue
            r = _sync_one(a["id"], force=True)
            if r:
                total.update(r)
        with _IMAP_LOCK:
            IMAP.update(running=False, last_run=time.time(), last_result=dict(total), current="")
    finally:
        with _IMAP_LOCK:
            IMAP["running"] = False
        _SYNC_LOCK.release()


def _imap_loop():
    time.sleep(20)
    while True:
        try:
            _sync_all()
        except Exception:
            pass
        time.sleep(30)


@app.route("/api/inbox")
def api_inbox():
    a = request.args
    per = max(10, min(int(a.get("per", 40) or 40), 1000))
    return jsonify({**store.inbox_list(a.get("box", ""), a.get("q", ""), int(a.get("page", 0) or 0), per),
                    "counts": store.inbox_counts()})


@app.route("/api/inbox/<int:iid>")
def api_inbox_item(iid):
    it = store.inbox_get(iid)
    if not it:
        return jsonify({}), 404
    it["thread"] = store.inbox_thread(it.get("contact_id"))
    it["contact"] = store.contact_detail(it["contact_id"]) if it.get("contact_id") else None
    if it["contact"]:
        it["contact"].pop("sends", None)
        it["contact"].pop("events", None)
    return jsonify(it)


@app.route("/api/inbox/<int:iid>", methods=["POST"])
def api_inbox_update(iid):
    kw = {}
    if "label" in request.form:
        kw["label"] = _s("label")
    for k in ("is_read", "archived"):
        if k in request.form:
            kw[k] = 1 if _s(k) == "1" else 0
    store.inbox_update(iid, **kw)
    if kw.get("label") == "unsubscribe":
        it = store.inbox_get(iid, mark_read=False)
        if it and it.get("contact_id"):
            store.unsubscribe_by_id(it["contact_id"], "reply request")
    return jsonify({"ok": True})


@app.route("/api/inbox/read-all", methods=["POST"])
def api_inbox_read_all():
    store.inbox_mark_all_read()
    return jsonify({"ok": True})


@app.route("/api/inbox/<int:iid>/reply", methods=["POST"])
def api_inbox_reply(iid):
    it = store.inbox_get(iid, mark_read=False)
    body = _s("body")
    if not it or not body:
        return jsonify({"ok": False, "error": "Write a reply first."}), 400
    a = store.get_account(it.get("account_id") or 0)
    if not a:
        accs = store.accounts(hide_pw=False)
        a = store.get_account(accs[0]["id"]) if accs else None
    if not a:
        return jsonify({"ok": False, "error": "No sender account available."}), 400
    subj = it.get("subject") or ""
    if not subj.lower().startswith("re:"):
        subj = "Re: " + subj
    html = "<div style=\"font-family:Arial,sans-serif;font-size:14px;line-height:1.6\">" + \
        _html.escape(body).replace("\n", "<br>") + "</div>"
    try:
        s = mailer.SMTPSender(a["host"], a["port"], a["security"], a["username"], a["password"])
        s.connect()
        mid = s.send(from_name=a["from_name"], from_email=a["from_email"], reply_to=a["reply_to"],
                     to_email=it["from_email"], subject=subj, html=html, text=body,
                     in_reply_to=it.get("message_id", ""), references=it.get("references_", ""))
        s.quit()
    except mailer.MailerError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Could not send ({e})."}), 400
    store.inbox_add({"account_id": a["id"], "contact_id": it.get("contact_id", 0),
                     "campaign_id": it.get("campaign_id", 0), "kind": "outgoing",
                     "from_email": a["from_email"], "from_name": a.get("from_name", ""),
                     "subject": subj, "snippet": body[:300], "body": body, "message_id": mid,
                     "is_read": 1})
    return jsonify({"ok": True, "message": f"Reply sent to {it['from_email']}."})


@app.route("/api/inbox/sync", methods=["POST"])
def api_inbox_sync():
    if not any(a.get("imap_enabled") for a in store.accounts()):
        return jsonify({"ok": False, "error": "Turn on inbox sync (IMAP) for at least one sender "
                                              "in Senders first."}), 400
    threading.Thread(target=_sync_all, args=(True,), daemon=True).start()
    return jsonify({"ok": True})


@app.route("/api/inbox/status")
def api_inbox_status():
    with _IMAP_LOCK:
        d = dict(IMAP)
    d["counts"] = store.inbox_counts()
    d["accounts"] = [{"id": a["id"], "email": a["from_email"], "enabled": a["imap_enabled"],
                      "last": a["imap_last_check"], "error": a["imap_error"]}
                     for a in store.accounts()]
    return jsonify(d)


# ------------------------------ tracking + unsub ---------------------------- #
@app.route("/t/o/<int:cid>/<int:coid>.gif")
def track_open(cid, coid):
    try:
        store.log_event(cid, coid, "open")
    except Exception:
        pass
    return Response(_PIXEL, mimetype="image/gif",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@app.route("/t/c/<int:cid>/<int:coid>")
def track_click(cid, coid):
    url = request.args.get("u", "")
    try:
        store.log_event(cid, coid, "click", url)
        if coid and cid not in (0,) and coid not in store.openers_of(cid):
            store.log_event(cid, coid, "open", "via click")   # images were blocked
    except Exception:
        pass
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "/"
    return redirect(url, code=302)


_UNSUB_PAGE = """<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title>
<style>body{{font-family:-apple-system,Segoe UI,Arial,sans-serif;background:#f5f6fa;color:#1f2937;
margin:0;display:grid;place-items:center;min-height:100vh}}.b{{background:#fff;border-radius:16px;
padding:40px 36px;max-width:440px;text-align:center;box-shadow:0 10px 30px rgba(0,0,0,.08)}}
h1{{font-size:22px;margin:0 0 10px}}p{{color:#6b7280;line-height:1.6}}button{{background:#4f46e5;
color:#fff;border:0;border-radius:10px;padding:13px 26px;font-size:15px;font-weight:700;cursor:pointer;
margin-top:12px}}</style></head><body><div class='b'>{body}</div></body></html>"""


@app.route("/u/<int:cid>/<int:coid>", methods=["GET", "POST"])
def unsub_page(cid, coid):
    # GET only asks — link scanners (Outlook Safe Links etc.) prefetch URLs and must not
    # unsubscribe people. POST (the button, or RFC 8058 one-click) does it.
    if request.method == "POST":
        store.unsubscribe_by_id(coid, "unsubscribed")
        try:
            store.log_event(cid, coid, "unsub")
        except Exception:
            pass
        return Response(_UNSUB_PAGE.format(title="Unsubscribed", body=(
            "<h1>You're unsubscribed ✅</h1><p>You won't receive any more emails from us. "
            "Sorry to see you go.</p>")), mimetype="text/html")
    return Response(_UNSUB_PAGE.format(title="Unsubscribe", body=(
        "<h1>Unsubscribe?</h1><p>Click below and you won't receive any more emails from us.</p>"
        "<form method='post'><button type='submit'>Yes, unsubscribe me</button></form>")),
        mimetype="text/html")


# ------------------------------ export -------------------------------------- #
@app.route("/api/export/contacts.csv")
def export_contacts():
    return Response(store.export_contacts_csv(_filt_args(request.args)), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=contacts.csv"})


@app.route("/api/export/report/<int:cid>.csv")
def export_report(cid):
    return Response(store.campaign_report_csv(cid), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=campaign_{cid}.csv"})


# ------------------------------ sending engine ------------------------------ #
@app.route("/api/test-send", methods=["POST"])
def api_test_send():
    to = _s("to")
    if not to:
        return jsonify({"ok": False, "error": "Enter an address."}), 400
    ids = _ids("account_ids")
    accs = store.accounts_for(ids) or store.accounts(hide_pw=False)
    if not accs:
        return jsonify({"ok": False, "error": "Add a sender account first."}), 400
    a = store.get_account(accs[0]["id"])
    sample = {"email": to, "first_name": "Test", "last_name": "User", "data": {"company": "Acme"}}
    subject = mailer.personalize(_s("subject", "(no subject)"), sample)
    html = mailer.inject_tracking(mailer.personalize(_s("html"), sample), "", 0, 0, False, False,
                                  f"mailto:{a['reply_to'] or a['from_email']}?subject=unsubscribe")
    try:
        s = mailer.SMTPSender(a["host"], a["port"], a["security"], a["username"], a["password"])
        s.connect()
        s.send(from_name=a["from_name"], from_email=a["from_email"], reply_to=a["reply_to"],
               to_email=to, subject="[TEST] " + subject, html=html,
               text=mailer.personalize(_s("text"), sample), unsub_mailto=a["from_email"])
        s.quit()
        return jsonify({"ok": True, "message": f"Test sent to {to} via {a['from_email']}."})
    except mailer.MailerError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": f"Could not send ({e})."}), 400


def _window():
    st = store.get_settings()
    try:
        return int(st.get("sending_window_start", "0") or 0), int(st.get("sending_window_end", "24") or 24)
    except ValueError:
        return 0, 24


def _within_window():
    s, e = _window()
    if s == 0 and e == 24:
        return True
    h = time.localtime().tm_hour
    return s <= h < e if s <= e else (h >= s or h < e)


class _Senders:
    """Rotating pool of sender accounts for one campaign run."""

    def __init__(self, account_ids):
        self.ids = account_ids
        self.pool = []
        self.i = 0
        self.refresh()

    def refresh(self):
        self.close()
        self.at = time.time()
        self.pool = [{"acc": a, "sender": None, "sent": a["sent_today"], "limit": a["effective_limit"],
                      "consec": 0, "dropped": False, "error": ""}
                     for a in store.accounts_for(self.ids)]

    def usable(self):
        return [p for p in self.pool if not p["dropped"]]

    def has_budget(self):
        return any(p["sent"] < p["limit"] for p in self.usable())

    def next(self):
        n = len(self.pool)
        for _ in range(n):
            p = self.pool[self.i % n]
            self.i += 1
            if p["dropped"] or p["sent"] >= p["limit"]:
                continue
            if p["sender"] is None:
                a = p["acc"]
                try:
                    s = mailer.SMTPSender(a["host"], a["port"], a["security"], a["username"],
                                          a["password"])
                    s.connect()
                    p["sender"] = s
                except mailer.MailerError as e:
                    self.fail(p, str(e))
                    continue
            return p
        return None

    def ok(self, p):
        p["sent"] += 1
        p["consec"] = 0
        store.incr_account(p["acc"]["id"])

    def fail(self, p, err):
        p["consec"] += 1
        p["error"] = err[:200]
        if p["consec"] >= SENDER_MAX_CONSEC and not p["dropped"]:
            p["dropped"] = True
            if p["sender"]:
                p["sender"].quit()
                p["sender"] = None
            store.set_account_fields(p["acc"]["id"], paused_reason=(
                f"Auto-paused after {p['consec']} failures in a row: {err}")[:300])

    def revive(self):
        for p in self.pool:
            if p["dropped"]:
                p.update(dropped=False, consec=0)
                store.set_account_fields(p["acc"]["id"], paused_reason="")

    def summary(self):
        return [{"id": p["acc"]["id"], "email": p["acc"]["from_email"], "sent": p["sent"],
                 "limit": p["limit"], "dropped": p["dropped"], "error": p["error"]} for p in self.pool]

    def close(self):
        for p in self.pool:
            if p["sender"]:
                p["sender"].quit()
                p["sender"] = None


class _Brakes:
    """Automatic safety brakes: pause a campaign before it burns the sender's reputation."""

    def __init__(self, cid, st, enabled):
        n = lambda k, d: store.setting_num(st, k, d)  # noqa: E731
        self.cid = cid
        self.on = bool(enabled) and st.get("brake_enabled", "1") == "1"
        self.bounce_pct = n("brake_bounce_pct", 5)
        self.min_sample = max(10, int(n("brake_min_sample", 50)))
        self.fail_pct = n("brake_fail_pct", 30)
        self.consec_max = max(3, int(n("brake_consec_fail", 10)))
        self.complaints = int(n("brake_complaints", 3))
        self.unsub_pct = n("brake_unsub_pct", 5)
        self.reset(0, 0)

    def reset(self, sent, bounced):
        self.base = store.campaign_health(self.cid)
        self.base_sent = sent
        self.window = collections.deque(maxlen=50)
        self.consec = 0
        self.n = 0

    def record(self, ok):
        self.window.append(bool(ok))
        self.consec = 0 if ok else self.consec + 1
        self.n += 1

    def check(self, sent):
        if not self.on:
            return None
        if self.consec >= self.consec_max:
            return (f"{self.consec} sends failed in a row — your sender account or connection "
                    "has a problem. Check Senders, then resume.")
        w = len(self.window)
        if w >= 20 and self.fail_pct > 0:
            fp = self.window.count(False) / w * 100
            if fp >= self.fail_pct:
                return (f"{fp:.0f}% of the last {w} sends failed (limit {self.fail_pct:g}%). "
                        "The provider may be throttling or blocking you.")
        if self.n % 10 == 0:
            h = store.campaign_health(self.cid)
            s = max(0, sent - self.base_sent)
            hard = h["hard"] - self.base["hard"]
            denom = s + hard
            if self.bounce_pct > 0 and denom >= self.min_sample and hard / denom * 100 >= self.bounce_pct:
                return (f"Bounce rate hit {hard / denom * 100:.1f}% ({hard} of {denom}) — above your "
                        f"{self.bounce_pct:g}% limit. Verify/clean this list before continuing.")
            comp = h["complaints"] - self.base["complaints"]
            if self.complaints > 0 and comp >= self.complaints:
                return (f"{comp} spam complaints received — recipients are marking this as spam. "
                        "Review your content and targeting.")
            un = h["unsubs"] - self.base["unsubs"]
            if self.unsub_pct > 0 and s >= self.min_sample and un / s * 100 >= self.unsub_pct:
                return (f"Unsubscribe rate hit {un / s * 100:.1f}% (limit {self.unsub_pct:g}%). "
                        "The message may not fit this audience.")
        return None


def _setj(cid, **kw):
    with _JOBS_LOCK:
        JOBS.setdefault(cid, {}).update(**kw)


def _trip(cid, reason):
    with _JOBS_LOCK:
        j = JOBS.setdefault(cid, {})
        j.update(pause=True, brake=reason, paused_by="brake", brake_at=time.time())
    store.set_campaign_field(cid, brake_reason=reason[:500])


def _run_campaign(cid, camp, recipients, resume=False):
    try:
        _run_campaign_inner(cid, camp, recipients, resume)
    except Exception as e:
        import traceback
        traceback.print_exc()
        _setj(cid, status="error", error=f"{type(e).__name__}: {e}")
        try:
            store.set_campaign_status(cid, "error")
        except Exception:
            pass


def _gate(cid, brakes, senders, counters):
    """Block until this campaign may send the next email. False = stop."""
    last_refresh = time.time()
    waiting = None
    while True:
        with _JOBS_LOCK:
            j = JOBS.get(cid, {})
            stop, paused = j.get("stop"), j.get("pause")
            reset = j.pop("brake_reset", False)
        if reset:
            brakes.reset(counters["sent"], counters["bounced"])
            senders.revive()
            store.set_campaign_field(cid, brake_reason="")
        if stop:
            return False
        if paused:
            time.sleep(0.5)
            continue
        if time.time() - senders.at > 300:
            senders.refresh()      # pick up senders turned off/paused/edited mid-campaign
        if not senders.usable():
            _trip(cid, "Every selected sender was auto-paused after repeated failures. "
                       "Check them in Senders (test the connection), then resume.")
            continue
        if not _within_window():
            s, e = _window()
            waiting = f"Outside your sending window ({s}:00–{e}:00) — resumes automatically."
        elif not senders.has_budget():
            waiting = ("Daily limit reached on all selected senders — continues automatically "
                       "tomorrow (or add senders / raise limits).")
            if time.time() - last_refresh > 60:
                senders.refresh()          # new day, raised limit or warm-up step
                last_refresh = time.time()
        else:
            if waiting:
                _setj(cid, waiting=None)
            return True
        _setj(cid, waiting=waiting, senders=senders.summary())
        time.sleep(3)


def _run_campaign_inner(cid, camp, recipients, resume=False):
    st = store.get_settings()
    mode, base = _tracking_mode()
    store.set_campaign_field(cid, tracking=mode)
    rate = int(camp.get("rate") or 60)
    jitter = float(camp.get("jitter") or 0)
    delay = 60.0 / max(1, min(rate, 6000))
    soft_limit = int(store.setting_num(st, "soft_bounce_limit", 3))
    try:
        account_ids = json.loads(camp.get("account_ids") or "[]")
    except Exception:
        account_ids = []
    subject_b = (camp.get("subject_b") or "").strip()
    prev = store.send_counts(cid) if resume else {}
    k = {"sent": prev.get("sent", 0), "failed": prev.get("failed", 0),
         "skipped": prev.get("skipped", 0), "bounced": prev.get("bounced", 0)}
    already = sum(k.values())
    total = len(recipients) + already
    t0 = time.time()

    senders = _Senders(account_ids)
    if not senders.pool:
        msg = ("No usable sender accounts — make sure the selected senders are active and "
               "not auto-paused (see Senders).")
        _setj(cid, status="error", error=msg)
        store.update_campaign_counts(cid, k["sent"], k["failed"], k["skipped"], "error")
        return
    brakes = _Brakes(cid, st, camp.get("brakes", 1))
    _setj(cid, total=total, **k)
    last_flush = time.time()
    i = 0
    while i < len(recipients):
        if not _gate(cid, brakes, senders, k):
            break
        r = recipients[i]
        email = r["email"]
        if store.contact_status(r["id"]) != "active":   # unsubscribed/bounced mid-campaign
            k["skipped"] += 1
            store.log_send(cid, r["id"], email, "skipped", "A", "not active")
            i += 1
            continue
        variant = "B" if (subject_b and random.random() < 0.5) else "A"
        subject = mailer.personalize(subject_b if variant == "B" else camp["subject"], r)
        body = mailer.personalize(camp["html"], r)
        text = mailer.personalize(camp.get("text") or "", r)
        outcome, err, attempts, used = None, "", 0, None
        while attempts < 3:
            p = senders.next()
            if p is None:
                break
            a = p["acc"]
            used = a["id"]
            if mode == "full":      # own public URL: tracked links + web unsubscribe page
                unsub = f"{base}/u/{cid}/{r['id']}"
                html = mailer.inject_tracking(body, base, cid, r["id"], bool(camp["track_opens"]),
                                              bool(camp["track_clicks"]), unsub)
            else:                   # links stay original; unsubscribe by email reply
                unsub = f"mailto:{a['reply_to'] or a['from_email']}?subject=unsubscribe"
                html = mailer.inject_tracking(body, base, cid, r["id"],
                                              mode == "opens" and bool(camp["track_opens"]),
                                              False, unsub)
            try:
                mid = p["sender"].send(from_name=a["from_name"], from_email=a["from_email"],
                                       reply_to=a["reply_to"], to_email=email, subject=subject,
                                       html=html, text=text, unsub_mailto=a["from_email"],
                                       unsub_url=unsub)
                senders.ok(p)
                k["sent"] += 1
                store.log_send(cid, r["id"], email, "sent", variant, "", mid, a["id"])
                brakes.record(True)
                outcome = "sent"
                break
            except mailer.RecipientError as e:
                p["consec"] = 0          # the server answered; the sender is fine
                store.record_bounce(email, e.kind, e.code, str(e), "smtp", cid, r["id"], soft_limit)
                if e.kind == "hard":
                    k["bounced"] += 1
                    store.log_send(cid, r["id"], email, "bounced", variant, str(e)[:300], "", a["id"])
                else:
                    k["failed"] += 1
                    store.log_send(cid, r["id"], email, "failed", variant, str(e)[:300], "", a["id"])
                brakes.record(True)
                outcome = "bounced"
                break
            except mailer.MailerError as e:
                senders.fail(p, str(e))
                err = str(e)
                attempts += 1
            except Exception as e:      # never let one bad recipient kill the run
                err = f"{type(e).__name__}: {e}"
                attempts += 1
        if outcome is None:
            if attempts == 0:
                continue                # no sender free right now -> gate waits/brakes; retry same
            k["failed"] += 1
            store.log_send(cid, r["id"], email, "failed", variant, err[:300], "", used or 0)
            brakes.record(False)
        i += 1
        done = sum(k.values())
        el = max(0.1, time.time() - t0)
        cr = (done - already) / el * 60
        _setj(cid, current=email, rate=round(cr), senders=senders.summary(),
              eta=round((total - done) / max(cr, 1) * 60), **k)
        if time.time() - last_flush > 5:
            store.update_campaign_counts(cid, k["sent"], k["failed"], k["skipped"])
            last_flush = time.time()
        reason = brakes.check(k["sent"])
        if reason:
            _trip(cid, reason)
        time.sleep(delay + (random.uniform(0, jitter) if jitter else 0))

    senders.close()
    with _JOBS_LOCK:
        final = "stopped" if JOBS.get(cid, {}).get("stop") else "done"
        JOBS.setdefault(cid, {}).update(status=final, current="", waiting=None, pause=False)
    store.update_campaign_counts(cid, k["sent"], k["failed"], k["skipped"], final)


def _start_job(cid, camp, recipients, resume=False):
    with _JOBS_LOCK:
        JOBS[cid] = {"status": "running", "campaign_id": cid, "name": camp.get("name", ""),
                     "total": len(recipients), "sent": 0, "failed": 0, "skipped": 0, "bounced": 0,
                     "current": "", "error": None, "started": time.time(), "pause": False,
                     "stop": False, "rate": 0, "eta": 0, "brake": None, "waiting": None,
                     "senders": []}
    store.set_campaign_status(cid, "running")
    store.set_campaign_field(cid, brake_reason="")
    threading.Thread(target=_run_campaign, args=(cid, camp, recipients, resume), daemon=True).start()


def _campaign_recipients(camp):
    if camp.get("parent_id"):
        return _followup_recipients(camp)
    g, ex = store.campaign_groups(camp)
    return store.recipients_for(g, exclude_group_ids=ex)


@app.route("/api/campaign/send", methods=["POST"])
def api_campaign_send():
    if not store.accounts(hide_pw=False):
        return jsonify({"ok": False, "error": "Add a sender account first."}), 400
    subject, html = _s("subject"), _s("html")
    if not subject or not html:
        return jsonify({"ok": False, "error": "Add a subject and content first."}), 400
    group_ids = _ids("group_ids")
    if not group_ids and _s("list_id").isdigit():
        group_ids = [int(_s("list_id"))]
    exclude = _ids("exclude_group_ids")
    account_ids = _ids("account_ids")
    recipients = store.recipients_for(group_ids, exclude_group_ids=exclude)
    if not recipients:
        return jsonify({"ok": False, "error": "No active contacts match these groups."}), 400

    scheduled_at = 0.0
    if _s("scheduled_at"):
        try:
            scheduled_at = float(_s("scheduled_at"))
        except ValueError:
            scheduled_at = 0.0

    cd = {"name": _s("name", "Campaign"), "subject": subject, "subject_b": _s("subject_b"),
          "html": html, "text": _s("text"), "group_ids": group_ids, "exclude_group_ids": exclude,
          "account_ids": account_ids,
          "track_opens": 1 if _s("track_opens", "1") == "1" else 0,
          "track_clicks": 1 if _s("track_clicks", "1") == "1" else 0,
          "rate": int(float(_s("rate_per_min", "60") or 60)),
          "jitter": float(_s("jitter", "0") or 0), "brakes": 0 if _s("brakes", "1") == "0" else 1,
          "scheduled_at": scheduled_at,
          "status": "scheduled" if scheduled_at > time.time() else "draft"}
    cid = store.create_campaign(cd)

    try:
        followups = json.loads(_s("followups") or "[]")
    except Exception:
        followups = []
    start = max(scheduled_at, time.time())
    for i, fu in enumerate(followups, start=1):
        try:
            delay_h = float(fu.get("delay_hours") or 24)
        except Exception:
            delay_h = 24
        store.create_campaign({
            "name": f"{cd['name']} · Follow-up {i}", "subject": fu.get("subject") or subject,
            "html": fu.get("html") or html, "text": fu.get("text") or "",
            "group_ids": group_ids, "exclude_group_ids": exclude,
            "account_ids": account_ids, "track_opens": cd["track_opens"],
            "track_clicks": cd["track_clicks"], "rate": cd["rate"], "jitter": cd["jitter"],
            "brakes": cd["brakes"], "parent_id": cid, "step_no": i,
            "send_to": fu.get("send_to") or "non_openers",
            "scheduled_at": start + delay_h * 3600, "status": "scheduled"})

    if scheduled_at > time.time():
        return jsonify({"ok": True, "scheduled": True, "campaign_id": cid})
    if _running_count() >= MAX_CONCURRENT:
        store.set_campaign_status(cid, "queued")
        return jsonify({"ok": True, "queued": True, "campaign_id": cid})
    _start_job(cid, store.get_campaign(cid), recipients)
    return jsonify({"ok": True, "campaign_id": cid, "total": len(recipients)})


@app.route("/api/campaign/control", methods=["POST"])
def api_campaign_control():
    cid = int(_s("campaign_id", "0") or 0)
    action = _s("action")
    with _JOBS_LOCK:
        j = JOBS.get(cid)
        if j:
            if action == "pause":
                j["pause"] = True
                j["paused_by"] = "user"
            elif action == "resume":
                j["pause"] = False
                if j.get("brake"):
                    j["brake"] = None
                    j["brake_reset"] = True
            elif action == "stop":
                j["stop"] = True
    return jsonify({"ok": True})


@app.route("/api/campaign/<int:cid>/resume-run", methods=["POST"])
def api_campaign_resume_run(cid):
    """Continue an interrupted/stopped campaign — only people not yet emailed."""
    camp = store.get_campaign(cid)
    if not camp:
        abort(404)
    if _is_running(cid):
        return jsonify({"ok": False, "error": "It's already sending."}), 400
    if _running_count() >= MAX_CONCURRENT:
        return jsonify({"ok": False, "error": "Too many campaigns running — try again shortly."}), 400
    done = store.logged_contacts_of(cid)
    recips = [r for r in _campaign_recipients(camp) if r["id"] not in done]
    if not recips:
        store.set_campaign_status(cid, "done")
        return jsonify({"ok": True, "nothing": True})
    _start_job(cid, camp, recips, resume=True)
    return jsonify({"ok": True, "remaining": len(recips)})


@app.route("/api/campaign/<int:cid>")
def api_campaign_get(cid):
    c = store.get_campaign(cid)
    if not c:
        return jsonify({}), 404
    c["group_ids"], c["exclude_group_ids"] = store.campaign_groups(c)
    try:
        c["account_ids"] = json.loads(c.get("account_ids") or "[]")
    except Exception:
        c["account_ids"] = []
    c["followups"] = [{"delay_hours": round(((ch.get("scheduled_at") or 0) - (c.get("scheduled_at") or
                                                                         c.get("created_at") or 0)) / 3600) or 48,
                       "subject": ch["subject"], "html": ch["html"], "text": ch.get("text") or "",
                       "send_to": ch.get("send_to") or "non_openers"}
                      for ch in [store.get_campaign(x["id"]) for x in
                                 store.campaign_report(cid).get("children", [])] if ch]
    return jsonify(c)


@app.route("/api/campaign/<int:cid>/delete", methods=["POST"])
def api_campaign_delete(cid):
    if _is_running(cid):
        return jsonify({"ok": False, "error": "Stop the campaign before deleting it."}), 400
    store.delete_campaign(cid)
    with _JOBS_LOCK:
        JOBS.pop(cid, None)
    return jsonify({"ok": True})


@app.route("/api/campaign/<int:cid>/cancel", methods=["POST"])
def api_campaign_cancel(cid):
    """Cancel a scheduled/queued campaign (or a pending follow-up)."""
    c = store.get_campaign(cid)
    if c and c["status"] in ("scheduled", "queued"):
        store.set_campaign_status(cid, "cancelled")
    return jsonify({"ok": True})


@app.route("/api/campaign/status/<int:cid>")
def api_campaign_status(cid):
    with _JOBS_LOCK:
        j = JOBS.get(cid)
    if j:
        return jsonify(dict(j))
    camp = store.get_campaign(cid)
    return jsonify({"status": camp["status"] if camp else "unknown", "campaign_id": cid})


@app.route("/api/campaigns/running")
def api_running():
    with _JOBS_LOCK:
        return jsonify({cid: dict(j) for cid, j in JOBS.items()})


@app.route("/api/report/<int:cid>")
def api_report(cid):
    r = store.campaign_report(cid)
    return (jsonify(r), 200) if r else (jsonify({}), 404)


# ------------------------------ scheduler ----------------------------------- #
def _followup_recipients(camp):
    parent_id = camp.get("parent_id") or 0
    sent = store.sent_contacts_of(parent_id)
    if not sent:
        return []
    send_to = camp.get("send_to") or "all"
    if send_to in ("openers", "non_openers"):
        openers = store.openers_of(parent_id)
        only = (sent & openers) if send_to == "openers" else (sent - openers)
    else:
        only = sent
    if store.get_settings().get("stop_followups_on_reply", "1") == "1":
        only = only - store.repliers_of_sequence(parent_id)
    return store.recipients_for(None, only=only)


def _scheduler_loop():
    while True:
        try:
            if _running_count() < MAX_CONCURRENT:
                for camp in store.due_campaigns():
                    if _running_count() >= MAX_CONCURRENT:
                        break
                    if _is_running(camp["id"]):
                        continue
                    if camp.get("parent_id"):
                        par = store.get_campaign(camp["parent_id"])
                        if par and par["status"] in ("running", "queued"):
                            continue      # wait until the parent has finished sending
                        if not par or par["status"] == "cancelled":
                            store.set_campaign_status(camp["id"], "cancelled")
                            continue
                    recips = _campaign_recipients(camp)
                    if recips:
                        _start_job(camp["id"], camp, recips)
                    else:
                        store.set_campaign_status(camp["id"], "done")
        except Exception:
            import traceback
            traceback.print_exc()
        time.sleep(15)


threading.Thread(target=_scheduler_loop, daemon=True).start()
threading.Thread(target=_imap_loop, daemon=True).start()


@app.errorhandler(413)
def too_large(e):
    return jsonify({"ok": False, "error": "File too large."}), 413


def _pick_port(preferred):
    import socket
    for p in [preferred] + list(range(preferred + 1, preferred + 20)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return preferred


def _redirect_logs_to_file():
    """Windowed build has no console — log to a file instead so libraries that
    write to stdout/stderr never crash on a missing console."""
    try:
        base = app_paths.data_dir() if app_paths else HERE
        f = open(os.path.join(base, "mailblaster.log"), "a", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = f
    except Exception:
        class _Null:
            def write(self, *a):
                pass

            def flush(self):
                pass
        sys.stdout = sys.stderr = _Null()


if __name__ == "__main__":
    frozen = getattr(sys, "frozen", False)
    # No console (frozen .exe OR launched via pythonw) -> log to file so prints
    # never crash on a missing stdout.
    if frozen or sys.stdout is None:
        _redirect_logs_to_file()
    port = int(os.environ.get("PORT", "0")) or _pick_port(5055)
    LOCAL_URL = f"http://127.0.0.1:{port}"
    if store.get_settings().get("track_mode") == "auto":
        store.save_settings({"track_base": ""})          # old address is gone
        tunnel.start(port, _tunnel_url)
    import atexit
    atexit.register(tunnel.stop)
    print(f"\n  MailBlaster  ->  http://127.0.0.1:{port}\n")
    if os.environ.get("MB_NO_BROWSER") != "1":
        def _open():
            import time
            import webbrowser
            time.sleep(1.2)
            try:
                webbrowser.open(LOCAL_URL)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)
