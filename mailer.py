"""
Sending engine + deliverability helpers for MailBlaster.

  personalize()   : {{first_name}}, {{first_name|there}} (fallback), {{data.company}}
  inject_tracking(): open pixel + click-tracking + working unsubscribe link
  spam_check()    : simple content score so you fix issues before sending
  validate_email(): syntax + MX-record check (dnspython) to clean a list
  SMTPSender      : batching / throttle / retry / reconnect, one per sender account
"""

from __future__ import annotations

import re
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid
from urllib.parse import quote

PRESETS = {
    "gmail":    {"host": "smtp.gmail.com", "port": 587, "security": "starttls"},
    "outlook":  {"host": "smtp.office365.com", "port": 587, "security": "starttls"},
    "yahoo":    {"host": "smtp.mail.yahoo.com", "port": 465, "security": "ssl"},
    "zoho":     {"host": "smtp.zoho.com", "port": 587, "security": "starttls"},
    "sendgrid": {"host": "smtp.sendgrid.net", "port": 587, "security": "starttls"},
    "mailgun":  {"host": "smtp.mailgun.org", "port": 587, "security": "starttls"},
    "ses":      {"host": "email-smtp.us-east-1.amazonaws.com", "port": 587, "security": "starttls"},
    "brevo":    {"host": "smtp-relay.brevo.com", "port": 587, "security": "starttls"},
    "custom":   {"host": "", "port": 587, "security": "starttls"},
}

# {{ key }} or {{ key | fallback }}
_TOKEN_RE = re.compile(r"\{\{\s*([\w.]+)\s*(?:\|\s*([^}]*?)\s*)?\}\}")


class MailerError(Exception):
    """Sender-side problem (connection, auth, policy block) — the account's fault."""
    kind = "sender"
    code = ""


class RecipientError(MailerError):
    """The receiving server refused this recipient. kind: hard | soft."""

    def __init__(self, msg, kind="hard", code=""):
        super().__init__(msg)
        self.kind = kind
        self.code = str(code or "")


_BLOCK_RE = re.compile(r"spam|block|blacklist|blocklist|reputation|policy|denied|5\.7\.1|"
                       r"spamhaus|barracuda|rate limit|too many|throttl|suspicious|"
                       r"not authori[sz]ed|authentication required|dmarc|spf|dkim", re.I)
_UNKNOWN_RE = re.compile(r"user unknown|no such user|does not exist|unknown user|"
                         r"mailbox unavailable|not found|invalid recipient|recipient rejected|"
                         r"address rejected|no mailbox|unrouteable|5\.1\.\d|doesn't have|"
                         r"disabled|inactive", re.I)
_FULL_RE = re.compile(r"mailbox full|quota|insufficient storage|5\.2\.2", re.I)


def classify_smtp(code, text) -> str:
    """hard (address is dead) | soft (temporary) | blocked (the sender is refused)."""
    try:
        code = int(code)
    except (TypeError, ValueError):
        code = 0
    t = text.decode("utf-8", "ignore") if isinstance(text, bytes) else str(text or "")
    if _FULL_RE.search(t):
        return "soft"
    if 500 <= code < 600:
        if _UNKNOWN_RE.search(t):
            return "hard"
        if _BLOCK_RE.search(t):
            return "blocked"
        return "hard"
    if code in (421, 450, 451, 454) and _BLOCK_RE.search(t):
        return "blocked"
    return "soft"


def _txt(b):
    return b.decode("utf-8", "ignore") if isinstance(b, bytes) else str(b or "")


def html_to_text(html: str) -> str:
    import html as _h
    if not html:
        return ""
    t = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    t = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h[1-6]>|</li>|</tr>", "\n", t)
    t = re.sub(r"(?is)<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", r"\2 (\1)", t)
    t = re.sub(r"<[^>]+>", "", t)
    t = _h.unescape(t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n\s*\n+", "\n\n", t)
    return t.strip()


def personalize(template: str, contact: dict, extra: dict | None = None) -> str:
    if not template:
        return ""
    data = contact.get("data") or {}
    values = {
        "first_name": contact.get("first_name", ""),
        "last_name": contact.get("last_name", ""),
        "email": contact.get("email", ""),
        "name": (f"{contact.get('first_name','')} {contact.get('last_name','')}").strip(),
    }
    if extra:
        values.update(extra)

    def repl(m):
        key, fallback = m.group(1), m.group(2)
        if key == "unsubscribe":          # filled in later by inject_tracking()
            return m.group(0)
        val = ""
        if key.startswith("data.") and isinstance(data, dict):
            val = data.get(key[5:], "")
        elif key in values:
            val = values[key]
        elif isinstance(data, dict) and key in data:
            val = data[key]
        val = str(val).strip()
        return val if val else (fallback if fallback is not None else "")
    return _TOKEN_RE.sub(repl, template)


# --------------------------- tracking + unsubscribe ------------------------- #
_LINK_RE = re.compile(r'(<a\b[^>]*\bhref=)(["\'])(https?://[^"\']+)\2', re.I)


def inject_tracking(html: str, base: str, cid: int, coid: int,
                    track_opens: bool, track_clicks: bool, unsub_url: str) -> str:
    html = html or ""
    if track_clicks and base:
        def wrap(m):
            url = m.group(3)
            if "/t/c/" in url or "/u/" in url:
                return m.group(0)
            tracked = f"{base}/t/c/{cid}/{coid}?u={quote(url, safe='')}"
            return f"{m.group(1)}{m.group(2)}{tracked}{m.group(2)}"
        html = _LINK_RE.sub(wrap, html)
    # always give a working unsubscribe link if the template used {{unsubscribe}}
    if "{{unsubscribe}}" in html:
        html = html.replace("{{unsubscribe}}", unsub_url)
    elif unsub_url:
        foot = (f'<div style="font-size:11px;color:#888;margin-top:24px;text-align:center">'
                f'<a href="{unsub_url}" style="color:#888">Unsubscribe</a></div>')
        i = html.lower().rfind("</body>")
        html = html[:i] + foot + html[i:] if i != -1 else html + foot
    if track_opens and base:
        # Visible-but-invisible 1x1 image. Some clients skip images with display:none, and
        # content after </body></html> can be dropped, so it goes just before </body>.
        pixel = (f'<img src="{base}/t/o/{cid}/{coid}.gif" width="1" height="1" alt="" border="0" '
                 f'style="width:1px;height:1px;border:0;outline:none;text-decoration:none">')
        low = html.lower()
        i = low.rfind("</body>")
        html = html[:i] + pixel + html[i:] if i != -1 else html + pixel
    return html


# --------------------------- spam / content check --------------------------- #
_SPAM_WORDS = ["free", "guarantee", "act now", "limited time", "click here", "buy now",
               "cash", "winner", "congratulations", "100%", "risk-free", "urgent",
               "cheap", "credit", "loan", "viagra", "casino", "$$$", "earn money",
               "make money", "no cost", "double your", "extra income", "amazing"]


def spam_check(subject: str, html: str) -> dict:
    issues, score = [], 0
    text = re.sub(r"<[^>]+>", " ", html or "")
    body = (subject + " " + text).lower()
    found = sorted({w for w in _SPAM_WORDS if w in body})
    if found:
        score += min(len(found) * 6, 40)
        issues.append(f"Spammy words: {', '.join(found[:8])}")
    if subject and subject == subject.upper() and len(subject) > 4:
        score += 15
        issues.append("Subject is ALL CAPS")
    if subject.count("!") >= 2 or "!!!" in (subject + text):
        score += 10
        issues.append("Too many exclamation marks")
    if "{{" in (subject + html):
        score += 20
        issues.append("Unresolved merge tag left in content (check spelling)")
    if not re.search(r"unsubscribe", (html or "").lower()) and "{{unsubscribe}}" not in (html or ""):
        score += 25
        issues.append("No unsubscribe link — required for bulk email & hurts deliverability")
    if len(text.strip()) < 40:
        score += 10
        issues.append("Very little text content")
    links = len(re.findall(r"https?://", html or ""))
    if links > 15:
        score += 10
        issues.append("A lot of links")
    grade = "Great" if score < 20 else ("OK" if score < 45 else "Risky")
    return {"score": min(score, 100), "grade": grade, "issues": issues}


# --------------------------- email validation ------------------------------- #
_SYNTAX = re.compile(r"^[^@\s]+@([^@\s]+\.[^@\s]+)$")
_mx_cache: dict[str, bool] = {}


def validate_email(email: str, check_mx: bool = True) -> tuple[bool, str]:
    m = _SYNTAX.match((email or "").strip())
    if not m:
        return False, "bad syntax"
    if not check_mx:
        return True, "ok"
    domain = m.group(1).lower()
    if domain in _mx_cache:
        return _mx_cache[domain], "ok" if _mx_cache[domain] else "no MX record"
    try:
        import dns.resolver
        res = dns.resolver.Resolver()
        res.lifetime = res.timeout = 4.0
        answers = res.resolve(domain, "MX")
        ok = len(answers) > 0
    except Exception:
        try:
            import dns.resolver
            dns.resolver.resolve(domain, "A")
            ok = True
        except Exception:
            ok = False
    _mx_cache[domain] = ok
    return ok, "ok" if ok else "domain can't receive mail"


# --------------------------- SMTP sender ------------------------------------ #
class SMTPSender:
    def __init__(self, host, port, security, username, password):
        if not host:
            raise MailerError("No SMTP host configured. Add a sender account in Settings.")
        self.host, self.port = host, int(port or 587)
        self.security = (security or "starttls").lower()
        self.username, self.password = username, password
        self.smtp = None
        self._n = 0

    def connect(self):
        ctx = ssl.create_default_context()
        try:
            if self.security == "ssl":
                self.smtp = smtplib.SMTP_SSL(self.host, self.port, timeout=30, context=ctx)
            else:
                self.smtp = smtplib.SMTP(self.host, self.port, timeout=30)
                self.smtp.ehlo()
                if self.security == "starttls":
                    self.smtp.starttls(context=ctx)
                    self.smtp.ehlo()
            if self.username:
                self.smtp.login(self.username, self.password)
        except smtplib.SMTPAuthenticationError:
            raise MailerError("Login failed — check the username/password. "
                              "(Gmail/Outlook need an app password.)")
        except Exception as e:
            raise MailerError(f"Could not connect to {self.host}:{self.port} ({e}).")
        self._n = 0

    def quit(self):
        try:
            if self.smtp:
                self.smtp.quit()
        except Exception:
            pass
        self.smtp = None

    def verify(self):
        self.connect()
        self.quit()

    def send(self, *, from_name, from_email, reply_to, to_email, subject, html, text,
             unsub_mailto="", unsub_url="", message_id=None, in_reply_to="", references="",
             retries=2, reconnect_every=100):
        """Send one message and return its Message-ID. Raises RecipientError when the
        receiving server refuses the address, MailerError for sender-side problems."""
        if self.smtp is None:
            self.connect()
        domain = from_email.split("@")[-1] if "@" in (from_email or "") else None
        mid = message_id or make_msgid(domain=domain)
        msg = EmailMessage()
        msg["From"] = formataddr((from_name or "", from_email))
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = mid
        if reply_to:
            msg["Reply-To"] = reply_to
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"] = f"{references} {in_reply_to}".strip()
        unsub = []
        https_unsub = bool(unsub_url and unsub_url.startswith("https://"))
        if https_unsub:
            unsub.append(f"<{unsub_url}>")
        if unsub_mailto:
            unsub.append(f"<mailto:{unsub_mailto}?subject=unsubscribe>")
        if unsub:
            msg["List-Unsubscribe"] = ", ".join(unsub)
        if https_unsub:   # RFC 8058 one-click (Gmail/Yahoo bulk-sender requirement)
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
        msg.set_content(text or html_to_text(html) or "This email contains HTML content.")
        if html:
            msg.add_alternative(html, subtype="html")
        last = None
        for attempt in range(retries + 1):
            try:
                self.smtp.send_message(msg)
                self._n += 1
                if self._n >= reconnect_every:
                    self.quit()
                    self.connect()
                return mid
            except smtplib.SMTPRecipientsRefused as e:
                code, resp = next(iter(e.recipients.values()), (0, b""))
                kind = classify_smtp(code, resp)
                if kind == "blocked":
                    raise MailerError(f"Blocked by receiving server ({code} {_txt(resp)})"[:300])
                raise RecipientError(f"{code} {_txt(resp)}".strip()[:300], kind, code)
            except smtplib.SMTPSenderRefused as e:
                raise MailerError(f"Sender address refused ({e.smtp_code} {_txt(e.smtp_error)})"[:300])
            except smtplib.SMTPResponseException as e:
                txt = _txt(e.smtp_error)
                kind = classify_smtp(e.smtp_code, txt)
                if 500 <= e.smtp_code < 600:          # permanent — retrying won't help
                    if kind == "blocked":
                        raise MailerError(f"Blocked by receiving server ({e.smtp_code} {txt})"[:300])
                    raise RecipientError(f"{e.smtp_code} {txt}"[:300], kind, e.smtp_code)
                last = e
                try:
                    self.smtp.rset()
                except Exception:
                    pass
                time.sleep(2.0 * (attempt + 1))
            except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError,
                    ConnectionError, TimeoutError, OSError) as e:
                last = e
                self.quit()
                time.sleep(1.5 * (attempt + 1))
                try:
                    self.connect()
                except MailerError as ce:
                    last = ce
        if isinstance(last, smtplib.SMTPResponseException):   # still deferred (4xx)
            kind = classify_smtp(last.smtp_code, _txt(last.smtp_error))
            if kind == "blocked":
                raise MailerError(f"Deferred/throttled ({last.smtp_code} {_txt(last.smtp_error)})"[:300])
            raise RecipientError(f"{last.smtp_code} {_txt(last.smtp_error)}"[:300], "soft",
                                 last.smtp_code)
        raise MailerError(f"Failed after retries ({last}).")
