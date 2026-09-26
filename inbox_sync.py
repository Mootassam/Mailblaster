"""
IMAP inbox processing for MailBlaster: reads each sender account's mailbox
(read-only — nothing is marked as read or moved) and turns what it finds into

  * bounces      (DSN / "Undeliverable" reports)  -> contact marked bounced + suppressed
  * complaints   (ARF feedback-loop reports)      -> contact unsubscribed + suppressed
  * auto-replies (out-of-office etc.)             -> inbox, doesn't count as a reply
  * replies      (matched to the campaign by Message-ID or sender address)
                                                  -> unified inbox, stops follow-ups

Only messages that relate to your campaigns are stored; personal mail is ignored.
"""

from __future__ import annotations

import datetime as _dt
import email
import html as _html
import imaplib
import json
import re
import socket
import ssl
import time
from email import policy
from email.parser import HeaderParser
from email.utils import getaddresses, parseaddr, parsedate_to_datetime

import store

IMAP_PRESETS = {
    "smtp.gmail.com": ("imap.gmail.com", 993, "ssl"),
    "smtp.office365.com": ("outlook.office365.com", 993, "ssl"),
    "smtp-mail.outlook.com": ("outlook.office365.com", 993, "ssl"),
    "smtp.mail.yahoo.com": ("imap.mail.yahoo.com", 993, "ssl"),
    "smtp.zoho.com": ("imap.zoho.com", 993, "ssl"),
    "smtp.zoho.eu": ("imap.zoho.eu", 993, "ssl"),
    "smtp.yandex.com": ("imap.yandex.com", 993, "ssl"),
    "smtp.mail.me.com": ("imap.mail.me.com", 993, "ssl"),
}

MAX_PER_PASS = 400             # messages examined per folder per sync
FETCH_BYTES = 400_000          # partial fetch cap — DSN/ARF parts sit near the top

_BOUNCE_FROM = re.compile(r"mailer-daemon|postmaster|mail delivery|maildelivery|"
                          r"bounce|mail-daemon", re.I)
_BOUNCE_SUBJ = re.compile(r"undeliver|undelivered|delivery status notification|delivery failure|"
                          r"mail delivery failed|returned mail|failure notice|delivery has failed|"
                          r"could not be delivered|message not delivered|non.?delivery|"
                          r"delivery notification|rejected|address not found", re.I)
_AUTO_SUBJ = re.compile(r"^\s*(auto(matic)?[\s-]?(reply|response|antwort|r[ée]ponse)|"
                        r"out of (the )?office|ooo\b|away from|on vacation|vacation reply|"
                        r"abwesenheit|absence|fuera de la oficina|r[ée]ponse automatique)", re.I)
_STATUS_RE = re.compile(r"\b([245])\.(\d{1,3})\.(\d{1,3})\b")
_EMAIL_RE = re.compile(r"[\w.+'-]+@[\w-]+(?:\.[\w-]+)+")

_UNSUB_RE = re.compile(r"\b(unsubscribe|remove me|take me off|stop (emailing|sending|contacting)|"
                       r"opt.?out|do not (contact|email)|don'?t (contact|email) me|"
                       r"please remove|delete my (email|address))\b", re.I)
_NOT_INT_RE = re.compile(r"\b(not interested|no thanks|no thank you|not a fit|not right now|"
                         r"we'?re (all )?set|pass on this|not looking|no need)\b", re.I)
_MEET_RE = re.compile(r"\b(calendly\.com|book a (call|time|meeting)|schedule a (call|meeting)|"
                      r"let'?s (talk|chat|meet|schedule)|free (on|at|tomorrow)|available (on|at)|"
                      r"send (me )?(an )?invite|hop on a call|set up a (call|meeting))\b", re.I)
_INT_RE = re.compile(r"\b(interested|sounds (good|great|interesting)|tell me more|more info|"
                     r"send (me )?(more|details|pricing|info)|how much|pricing|what('s| is) the (cost|price)|"
                     r"yes,? please|love to|happy to (chat|talk))\b", re.I)


class SyncError(Exception):
    pass


# ------------------------------ connection ---------------------------------- #
def imap_settings(acc):
    host = (acc.get("imap_host") or "").strip()
    port = int(acc.get("imap_port") or 0)
    sec = (acc.get("imap_security") or "").strip().lower()
    if not host:
        p = IMAP_PRESETS.get((acc.get("host") or "").lower())
        if p:
            host, port, sec = p[0], port or p[1], sec or p[2]
    user = (acc.get("imap_user") or "").strip() or acc.get("username") or acc.get("from_email")
    pw = acc.get("imap_password") or acc.get("password") or ""
    return host, port or 993, sec or "ssl", user, pw


def connect(acc):
    host, port, sec, user, pw = imap_settings(acc)
    if not host:
        raise SyncError("No IMAP server set for this sender.")
    try:
        if sec == "ssl":
            m = imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=30)
        else:
            m = imaplib.IMAP4(host, port, timeout=30)
            if sec == "starttls":
                m.starttls(ssl_context=ssl.create_default_context())
    except (OSError, socket.timeout, imaplib.IMAP4.error) as e:
        raise SyncError(f"Could not reach {host}:{port} ({e}).")
    try:
        m.login(user, pw)
    except imaplib.IMAP4.error as e:
        try:
            m.logout()
        except Exception:
            pass
        raise SyncError(f"IMAP login failed for {user} — check the password "
                        f"(Gmail/Outlook need an app password and IMAP enabled). ({_s(e)})")
    return m


def test(acc):
    m = connect(acc)
    try:
        typ, data = m.select("INBOX", readonly=True)
        n = int(data[0]) if typ == "OK" and data and data[0] else 0
    finally:
        try:
            m.logout()
        except Exception:
            pass
    return n


def _s(x):
    if isinstance(x, bytes):
        return x.decode("utf-8", "ignore")
    if isinstance(x, (list, tuple)):
        return " ".join(_s(i) for i in x)
    return str(x)


def _quote_folder(f):
    f = f.strip()
    return f'"{f}"' if (" " in f or "[" in f) and not f.startswith('"') else f


# ------------------------------ parsing ------------------------------------- #
def _text_of(msg, limit=20000):
    """Best-effort readable text of a message (plain part first, else stripped HTML)."""
    plain, htm = None, None
    try:
        for part in msg.walk():
            if part.is_multipart():
                continue
            ct = part.get_content_type()
            if part.get_content_disposition() == "attachment":
                continue
            if ct == "text/plain" and plain is None:
                plain = _payload(part)
            elif ct == "text/html" and htm is None:
                htm = _payload(part)
    except Exception:
        pass
    if plain and plain.strip():
        return plain[:limit]
    if htm:
        t = re.sub(r"(?is)<(script|style).*?</\1>", " ", htm)
        t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", t)
        t = _html.unescape(re.sub(r"<[^>]+>", "", t))
        t = re.sub(r"[ \t]+", " ", t)
        return re.sub(r"\n\s*\n+", "\n\n", t).strip()[:limit]
    return ""


def _payload(part):
    """Decoded text of a part. Many mailers omit or mislabel the charset, so try the
    declared one, then UTF-8, then Windows-1252 rather than showing mojibake."""
    try:
        raw = part.get_payload(decode=True)
    except Exception:
        raw = None
    if raw is None:
        try:
            return part.get_content()
        except Exception:
            return str(part.get_payload() or "")
    cs = part.get_content_charset()
    for enc in [cs, "utf-8", "cp1252"]:
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")


def strip_quoted(text):
    """Drop the quoted original from a reply so the preview shows what they wrote."""
    out = []
    for line in (text or "").splitlines():
        s = line.strip()
        if re.match(r"^(On .+wrote:|Le .+a écrit|Am .+schrieb|El .+escribió|-{2,}\s*Original Message|"
                    r"_{5,}|From:\s.+|Sent from my )", s, re.I):
            break
        if s.startswith(">"):
            continue
        out.append(line)
    return "\n".join(out).strip()


def _msgids(v):
    return re.findall(r"<[^<>\s]+>", _s(v or ""))


def _date(msg):
    try:
        d = parsedate_to_datetime(msg.get("Date"))
        return d.timestamp()
    except Exception:
        return time.time()


def _dsn_recipients(msg):
    """[(email, status, diagnostic, action)] from a message/delivery-status part."""
    out = []
    for part in msg.walk():
        if part.get_content_type() != "message/delivery-status":
            continue
        blocks = []
        try:
            pl = part.get_payload()
            if isinstance(pl, list):
                blocks = pl
            else:
                blocks = [HeaderParser().parsestr(b) for b in re.split(r"\n\s*\n", _s(pl))]
        except Exception:
            blocks = []
        for b in blocks:
            try:
                rcpt = b.get("Final-Recipient") or b.get("Original-Recipient") or ""
            except Exception:
                continue
            if not rcpt:
                continue
            addr = rcpt.split(";", 1)[-1].strip().strip("<>").lower()
            status = (b.get("Status") or "").strip()
            diag = (b.get("Diagnostic-Code") or "").split(";", 1)[-1].strip()
            action = (b.get("Action") or "").strip().lower()
            if _EMAIL_RE.fullmatch(addr):
                out.append((addr, status, diag, action))
    return out


def _original_msgid(msg):
    for part in msg.walk():
        ct = part.get_content_type()
        try:
            if ct == "message/rfc822":
                pl = part.get_payload()
                inner = pl[0] if isinstance(pl, list) and pl else pl
                if inner is not None and inner.get("Message-ID"):
                    return inner.get("Message-ID").strip()
            elif ct in ("text/rfc822-headers", "message/rfc822-headers"):
                h = HeaderParser().parsestr(_payload(part) if not isinstance(part.get_payload(), list)
                                            else "")
                if h.get("Message-ID"):
                    return h.get("Message-ID").strip()
        except Exception:
            continue
    m = re.search(r"^Message-ID:\s*(<[^>]+>)", _text_of(msg, 200000), re.I | re.M)
    return m.group(1) if m else ""


def _kind_from_status(status, diag, fallback_text=""):
    s = status or ""
    m = _STATUS_RE.search(s) or _STATUS_RE.search(diag or "") or _STATUS_RE.search(fallback_text or "")
    code = m.group(0) if m else ""
    txt = f"{diag} {fallback_text}"[:3000]
    if code.startswith("5.2.2") or re.search(r"mailbox (is )?full|over quota|quota exceeded", txt, re.I):
        return "soft", code
    if code.startswith("4"):
        return "soft", code
    if code.startswith("5"):
        return "hard", code
    if re.search(r"temporar|try again|deferred|delayed", txt, re.I):
        return "soft", code
    return "hard", code


def classify(msg, account_email=""):
    """Returns a dict describing the message, or None when it isn't campaign-related mail."""
    ctype = msg.get_content_type()
    rtype = (msg.get_param("report-type") or "").lower() if ctype == "multipart/report" else ""
    frm_name, frm = parseaddr(_s(msg.get("From", "")))
    frm = (frm or "").lower()
    subject = _s(msg.get("Subject", "")).strip()

    # --- spam complaint (ARF feedback loop) ---
    if rtype == "feedback-report":
        who = ""
        for part in msg.walk():
            if part.get_content_type() == "message/feedback-report":
                t = _s(part.get_payload() if not isinstance(part.get_payload(), list)
                       else "\n".join(_s(p.as_string()) for p in part.get_payload()))
                m = re.search(r"Original-Rcpt-To:\s*<?([^>\s]+)", t, re.I)
                if m:
                    who = m.group(1).lower()
        return {"kind": "complaint", "recipients": [(who, "", "spam complaint", "failed")] if who else [],
                "orig_msgid": _original_msgid(msg), "subject": subject, "from": frm,
                "from_name": frm_name}

    # --- delivery status notification (bounce) ---
    is_dsn = rtype == "delivery-status"
    looks_bounce = bool(_BOUNCE_FROM.search(frm) or _BOUNCE_SUBJ.search(subject))
    if is_dsn or (looks_bounce and not msg.get("In-Reply-To") and _BOUNCE_FROM.search(frm)) or \
            (looks_bounce and msg.get("X-Failed-Recipients")):
        rcpts = [r for r in _dsn_recipients(msg) if r[3] in ("failed", "", "failure")]
        delayed = [r for r in _dsn_recipients(msg) if r[3] == "delayed"]
        if not rcpts and delayed:
            return None          # "still trying" warnings aren't bounces
        body = _text_of(msg, 60000)
        if not rcpts:
            xf = msg.get("X-Failed-Recipients")
            cand = [a.lower() for a in _EMAIL_RE.findall(_s(xf))] if xf else []
            if not cand:
                acct = (account_email or "").lower()
                cand = [a.lower() for a in _EMAIL_RE.findall(body)
                        if a.lower() != acct and not _BOUNCE_FROM.search(a)]
            seen = []
            for a in cand:
                if a not in seen:
                    seen.append(a)
            rcpts = [(a, "", body[:400], "failed") for a in seen[:5]]
        if rcpts:
            return {"kind": "bounce", "recipients": rcpts, "orig_msgid": _original_msgid(msg),
                    "subject": subject, "from": frm, "from_name": frm_name, "body": body}
        return None

    # --- auto-reply / out-of-office ---
    auto = _s(msg.get("Auto-Submitted", "")).lower()
    prec = _s(msg.get("Precedence", "")).lower()
    is_auto = ((auto and auto != "no") or msg.get("X-Autoreply") or msg.get("X-Autorespond")
               or "auto_reply" in prec or _AUTO_SUBJ.search(subject)
               or msg.get("X-Auto-Response-Suppress", "").lower() in ("all", "oof"))
    kind = "auto" if is_auto else "reply"
    return {"kind": kind, "subject": subject, "from": frm, "from_name": frm_name,
            "in_reply_to": _msgids(msg.get("In-Reply-To")),
            "references": _msgids(msg.get("References"))}


def suggest_label(text):
    t = text or ""
    if _UNSUB_RE.search(t):
        return "unsubscribe"
    if _NOT_INT_RE.search(t):
        return "not_interested"
    if _MEET_RE.search(t):
        return "meeting"
    if _INT_RE.search(t):
        return "interested"
    return ""


# ------------------------------ processing ---------------------------------- #
def process_message(acc, raw, st=None):
    """Classify one raw message and apply it. Returns a short result kind or None."""
    st = st or store.get_settings()
    try:
        msg = email.message_from_bytes(raw, policy=policy.default)
    except Exception:
        return None
    try:
        info = classify(msg, acc.get("from_email", ""))
    except Exception:
        return None
    if not info:
        return None
    soft_limit = int(store.setting_num(st, "soft_bounce_limit", 3))
    mid = _s(msg.get("Message-ID", "")).strip() or f"<nomsgid-{hash(raw[:2000])}>"
    received = _date(msg)

    if info["kind"] in ("bounce", "complaint"):
        orig = store.find_send_by_msgids([info.get("orig_msgid", "")]) if info.get("orig_msgid") else None
        applied = 0
        first_rcpt = ""
        for addr, status, diag, _a in info["recipients"]:
            if not addr:
                continue
            ct = store.find_contact(addr)
            if not ct and not store.last_send_to(addr):
                continue            # not someone we emailed — ignore
            if info["kind"] == "complaint":
                kind, code = "complaint", ""
            else:
                kind, code = _kind_from_status(status, diag, info.get("body", "")[:3000])
            camp = (orig or {}).get("campaign_id") if orig and orig.get("email") == addr else 0
            store.record_bounce(addr, kind, code, diag or info["subject"], "imap",
                                campaign_id=camp or 0, contact_id=ct["id"] if ct else 0,
                                soft_limit=soft_limit)
            applied += 1
            first_rcpt = first_rcpt or addr
        if not applied:
            return None
        ct = store.find_contact(first_rcpt) or {}
        store.inbox_add({"account_id": acc["id"], "contact_id": ct.get("id", 0),
                         "campaign_id": (orig or {}).get("campaign_id", 0), "kind": info["kind"],
                         "from_email": first_rcpt, "from_name": info.get("from_name", ""),
                         "subject": info["subject"], "snippet": (info.get("body") or "")[:300],
                         "body": (info.get("body") or "")[:20000], "received_at": received,
                         "message_id": mid, "is_read": 1})
        return info["kind"]

    # replies + auto-replies: link to a send by Message-ID first, then by address
    link = store.find_send_by_msgids(info.get("in_reply_to", []) + info.get("references", []))
    ct = store.find_contact(info["from"])
    if not link and ct:
        link = store.last_send_to(info["from"])
        if link and link.get("contact_id") != ct["id"]:
            link["contact_id"] = ct["id"]
    if not link:
        return None                 # unrelated personal mail — never stored
    contact_id = (ct or {}).get("id") or link.get("contact_id") or 0
    body = _text_of(msg)
    fresh = strip_quoted(body) or body
    label = suggest_label(info["subject"] + " " + fresh) if info["kind"] == "reply" else ""
    added = store.inbox_add({
        "account_id": acc["id"], "contact_id": contact_id, "campaign_id": link.get("campaign_id", 0),
        "kind": info["kind"], "from_email": info["from"], "from_name": info.get("from_name", ""),
        "subject": info["subject"], "snippet": re.sub(r"\s+", " ", fresh)[:300], "body": body,
        "received_at": received, "message_id": mid,
        "references": " ".join(info.get("references", []) + info.get("in_reply_to", [])),
        "label": label})
    if added and label == "unsubscribe" and st.get("auto_unsub_on_request", "1") == "1" and contact_id:
        store.unsubscribe_by_id(contact_id, "reply request")
        if link.get("campaign_id"):
            store.log_event(link["campaign_id"], contact_id, "unsub", "reply")
    return info["kind"] if added else None


def sync_account(acc, st=None, days_back=14):
    """One pass over the account's folders. Returns counts; raises SyncError."""
    st = st or store.get_settings()
    folders = [f.strip() for f in (acc.get("imap_folders") or "INBOX").split(",") if f.strip()]
    state = acc.get("imap_state") if isinstance(acc.get("imap_state"), dict) else {}
    counts = {"checked": 0, "reply": 0, "auto": 0, "bounce": 0, "complaint": 0}
    m = connect(acc)
    try:
        for folder in folders:
            try:
                typ, _ = m.select(_quote_folder(folder), readonly=True)
            except imaplib.IMAP4.error:
                typ = "NO"
            if typ != "OK":
                continue
            uv = _s((m.response("UIDVALIDITY")[1] or [b""])[0])
            fs = state.get(folder) or {}
            last = int(fs.get("last", 0)) if fs.get("uv") == uv else 0
            if last:
                typ, data = m.uid("search", None, f"UID {last + 1}:*")
            else:
                since = (_dt.date.today() - _dt.timedelta(days=days_back)).strftime("%d-%b-%Y")
                typ, data = m.uid("search", None, "SINCE", since)
            uids = sorted(int(x) for x in _s(data[0] if data else b"").split() if x.isdigit())
            uids = [u for u in uids if u > last][:MAX_PER_PASS]
            for u in uids:
                try:
                    typ, fd = m.uid("fetch", str(u), f"(BODY.PEEK[]<0.{FETCH_BYTES}>)")
                except imaplib.IMAP4.error:
                    continue
                raw = b""
                for item in fd or []:
                    if isinstance(item, tuple) and len(item) > 1 and isinstance(item[1], bytes):
                        raw = item[1]
                        break
                counts["checked"] += 1
                if raw:
                    try:
                        k = process_message(acc, raw, st)
                    except Exception:
                        k = None
                    if k in counts:
                        counts[k] += 1
                last = max(last, u)
            state[folder] = {"uv": uv, "last": last}
    finally:
        try:
            m.logout()
        except Exception:
            pass
        store.set_account_fields(acc["id"], imap_state=json.dumps(state))
    return counts
