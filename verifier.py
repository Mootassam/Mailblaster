"""
Robust email verification for MailBlaster.

verify_one() grades a single address so you can clean a list *before* launching a
campaign and stop bounces/spam-traps. It layers cheap, certain checks first and
only does the slow network checks when they add information:

    syntax  -> typo suggestion -> disposable / role / free provider
            -> MX lookup (does the domain accept mail at all?)
            -> optional SMTP mailbox probe (does *this* mailbox exist?) with
               catch-all detection.

Every address ends up in one of four buckets:

    deliverable    looks safe to send to
    risky          sendable but lower confidence (catch-all, role address,
                   free-provider mailbox we couldn't individually confirm)
    undeliverable  will bounce — bad syntax, dead domain, or the server
                   rejected the exact mailbox
    unknown        we couldn't tell (greylisting, timeouts, port 25 blocked)

Design rules that keep it *safe to trust*:

  * It never marks a big mailbox provider (Gmail, Outlook, Yahoo, …) as
    undeliverable from an SMTP probe — those servers lie / block probes, so a
    valid MX is treated as deliverable.
  * If outbound port 25 is blocked (common on home/office ISPs) every SMTP probe
    fails the same way; we detect that and fall back to the MX-only verdict
    instead of wrongly condemning the whole list.
  * Hard timeouts on DNS and every SMTP step — a verification pass can be slow
    but it can never hang.

Needs dnspython (already a MailBlaster dependency). Pure stdlib otherwise.
"""

from __future__ import annotations

import random
import re
import smtplib
import socket
import string
import time

# --------------------------------------------------------------------------- #
#  static data
# --------------------------------------------------------------------------- #
_SYNTAX = re.compile(r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)$")

# Local-parts that are almost always shared inboxes, not a person. Sendable, but
# lower value and more likely to complain — we flag them as "risky", never dead.
ROLE_LOCALS = {
    "info", "support", "sales", "admin", "administrator", "contact", "help",
    "office", "team", "hello", "hi", "mail", "email", "billing", "accounts",
    "accounting", "finance", "hr", "jobs", "careers", "recruitment", "marketing",
    "noreply", "no-reply", "donotreply", "do-not-reply", "postmaster", "webmaster",
    "abuse", "security", "privacy", "legal", "press", "media", "feedback",
    "enquiries", "inquiries", "service", "services", "orders", "order", "shop",
    "newsletter", "notifications", "notification", "system", "root", "dev",
}

# The big consumer providers. SMTP probing them is unreliable, so a good MX is
# enough to call them deliverable.
FREE_PROVIDERS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "yahoo.fr",
    "ymail.com", "rocketmail.com", "outlook.com", "hotmail.com", "hotmail.co.uk",
    "hotmail.fr", "live.com", "msn.com", "icloud.com", "me.com", "mac.com",
    "aol.com", "gmx.com", "gmx.net", "gmx.de", "mail.com", "protonmail.com",
    "proton.me", "pm.me", "zoho.com", "yandex.com", "yandex.ru", "qq.com",
    "163.com", "126.com", "naver.com", "hey.com",
}

# Known disposable / throwaway providers (a practical starter set).
DISPOSABLE_DOMAINS = {
    "mailinator.com", "guerrillamail.com", "guerrillamail.info", "sharklasers.com",
    "grr.la", "10minutemail.com", "tempmail.com", "temp-mail.org", "trashmail.com",
    "yopmail.com", "throwawaymail.com", "getnada.com", "nada.email", "dispostable.com",
    "maildrop.cc", "mailnesia.com", "fakeinbox.com", "tempinbox.com", "mohmal.com",
    "emailondeck.com", "33mail.com", "spamgourmet.com", "mailcatch.com", "inboxbear.com",
    "mintemail.com", "mytemp.email", "burnermail.io", "tempr.email", "moakt.com",
    "mailexpire.com", "spam4.me", "tmpmail.org", "tmpmail.net", "tempmailo.com",
    "1secmail.com", "1secmail.org", "1secmail.net", "emailfake.com", "fakemail.net",
    "mailpoof.com", "vomoto.com", "trashmail.de", "wegwerfmail.de", "einrot.com",
}

# Common domain typos -> the address the person almost certainly meant.
TYPO_FIXES = {
    "gmial.com": "gmail.com", "gmai.com": "gmail.com", "gmil.com": "gmail.com",
    "gmaill.com": "gmail.com", "gmail.co": "gmail.com", "gmal.com": "gmail.com",
    "gamil.com": "gmail.com", "gmeil.com": "gmail.com", "gnail.com": "gmail.com",
    "gmail.con": "gmail.com", "gmail.cmo": "gmail.com", "gmailcom": "gmail.com",
    "googlemail.co": "googlemail.com",
    "yahooo.com": "yahoo.com", "yaho.com": "yahoo.com", "yahoo.co": "yahoo.com",
    "yhaoo.com": "yahoo.com", "yahooo.co": "yahoo.com", "yaoo.com": "yahoo.com",
    "hotmial.com": "hotmail.com", "hotmai.com": "hotmail.com", "hotmil.com": "hotmail.com",
    "hotmal.com": "hotmail.com", "homail.com": "hotmail.com", "hotmail.co": "hotmail.com",
    "hotmail.con": "hotmail.com", "hotnail.com": "hotmail.com",
    "outlok.com": "outlook.com", "outloo.com": "outlook.com", "outlook.co": "outlook.com",
    "outllook.com": "outlook.com", "oulook.com": "outlook.com",
    "iclould.com": "icloud.com", "icloud.co": "icloud.com", "iclod.com": "icloud.com",
    "live.co": "live.com", "aol.co": "aol.com", "protonmai.com": "protonmail.com",
}


class _DomainInfo:
    """Per-domain facts cached for the length of a verification pass (and
    optionally persisted by the caller) so each domain is resolved once."""
    __slots__ = ("mx", "mx_hosts", "disposable", "catch_all", "smtp_ok", "checked_smtp")

    def __init__(self):
        self.mx = None            # True/False/None(unknown)
        self.mx_hosts = []
        self.disposable = False
        self.catch_all = None     # True/False/None(not probed / unknown)
        self.smtp_ok = None       # did any SMTP connection succeed at all?
        self.checked_smtp = False


# --------------------------------------------------------------------------- #
#  DNS
# --------------------------------------------------------------------------- #
def _resolve_mx(domain: str, timeout: float = 5.0):
    """Return (ok, hosts). ok=True with hosts, ok=False for a dead domain,
    ok=None when DNS itself failed (can't tell)."""
    try:
        import dns.resolver
    except Exception:
        # dnspython missing — fall back to a plain A lookup via sockets.
        try:
            socket.setdefaulttimeout(timeout)
            socket.gethostbyname(domain)
            return True, [domain]
        except Exception:
            return None, []
    res = dns.resolver.Resolver()
    res.lifetime = res.timeout = timeout
    try:
        ans = res.resolve(domain, "MX")
        hosts = sorted(((r.preference, str(r.exchange).rstrip(".")) for r in ans),
                       key=lambda x: x[0])
        hosts = [h for _, h in hosts if h]
        if hosts:
            return True, hosts
    except Exception as e:
        # NXDOMAIN / NoAnswer => domain is real-but-no-MX or doesn't exist.
        name = type(e).__name__
        if name in ("NXDOMAIN", "NoNameservers"):
            return False, []
        if name != "NoAnswer":
            return None, []     # timeout / network — unknown
    # No MX record: RFC allows falling back to the A record as the mail host.
    try:
        res.resolve(domain, "A")
        return True, [domain]
    except Exception as e:
        name = type(e).__name__
        if name in ("NXDOMAIN", "NoNameservers", "NoAnswer"):
            return False, []
        return None, []


# --------------------------------------------------------------------------- #
#  SMTP mailbox probe
# --------------------------------------------------------------------------- #
def _rcpt_code(smtp: smtplib.SMTP, addr: str):
    try:
        code, _ = smtp.rcpt(addr)
        return int(code)
    except Exception:
        return -1


def _smtp_probe(hosts, email, mail_from, helo_name, timeout, do_catch_all=True):
    """Ask the real mail server whether the mailbox exists.

    Returns a dict:
        connected : did we reach any server (port 25 reachable)?
        rcpt      : SMTP code for the real address (or None)
        catch_all : True/False/None — does the domain accept *anything*?
    """
    out = {"connected": False, "rcpt": None, "catch_all": None}
    domain = email.split("@", 1)[1]
    for host in hosts[:2]:
        smtp = smtplib.SMTP(timeout=timeout, local_hostname=helo_name or None)
        try:
            smtp.connect(host, 25)
            out["connected"] = True
            smtp.ehlo_or_helo_if_needed()
            try:
                smtp.docmd("MAIL FROM:", f"<{mail_from}>")
            except Exception:
                pass
            out["rcpt"] = _rcpt_code(smtp, email)
            if do_catch_all and out["rcpt"] in (250, 251):
                rnd = "".join(random.choices(string.ascii_lowercase + string.digits, k=20))
                cc = _rcpt_code(smtp, f"{rnd}@{domain}")
                out["catch_all"] = cc in (250, 251)
            try:
                smtp.quit()
            except Exception:
                pass
            return out
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError,
                socket.timeout, ConnectionError, OSError):
            try:
                smtp.close()
            except Exception:
                pass
            continue
        except Exception:
            try:
                smtp.close()
            except Exception:
                pass
            continue
    return out


# --------------------------------------------------------------------------- #
#  public API
# --------------------------------------------------------------------------- #
def _bucket(result, reason, score, **extra):
    d = {"result": result, "reason": reason, "score": int(max(0, min(100, score)))}
    d.update(extra)
    return d


def verify_one(email: str, *, mail_from: str = "verify@example.com",
               helo_name: str = "mail.local", deep: bool = True,
               cache: dict | None = None, dns_timeout: float = 5.0,
               smtp_timeout: float = 10.0) -> dict:
    """Grade one address. `cache` is a dict {domain: _DomainInfo} shared across a
    batch so each domain is resolved/probed once."""
    email = (email or "").strip().lower()
    base = {"email": email, "mx": False, "role": False, "disposable": False,
            "free": False, "catch_all": False, "did_smtp": False, "suggestion": ""}

    m = _SYNTAX.match(email)
    if not m:
        return {**base, **_bucket("undeliverable", "Invalid email syntax", 0)}
    local, domain = email.split("@", 1)

    # obvious typo in the domain -> treat as undeliverable but hand back the fix
    if domain in TYPO_FIXES:
        fix = f"{local}@{TYPO_FIXES[domain]}"
        return {**base, "suggestion": fix,
                **_bucket("undeliverable", f"Likely typo — did you mean {TYPO_FIXES[domain]}?", 5)}

    cache = cache if cache is not None else {}
    info = cache.get(domain)
    if info is None:
        info = _DomainInfo()
        info.disposable = domain in DISPOSABLE_DOMAINS
        ok, hosts = _resolve_mx(domain, dns_timeout)
        info.mx = ok
        info.mx_hosts = hosts
        cache[domain] = info

    role = local in ROLE_LOCALS
    free = domain in FREE_PROVIDERS
    base.update(role=role, free=free, disposable=info.disposable, mx=bool(info.mx))

    if info.disposable:
        return {**base, **_bucket("undeliverable",
                                  "Disposable / throwaway mailbox", 10)}
    if info.mx is False:
        return {**base, **_bucket("undeliverable",
                                  "Domain has no mail server (can't receive email)", 10)}
    if info.mx is None:
        return {**base, **_bucket("unknown",
                                  "Couldn't resolve the domain (DNS timeout)", 45)}

    # From here the domain can receive mail. Decide how confident we are.
    if not deep or free:
        # No SMTP probe (or a provider that blocks them): trust the MX.
        if free and role:
            return {**base, **_bucket("risky", "Role address on a shared/free mailbox", 60)}
        if role:
            return {**base, **_bucket("risky", "Role address (shared inbox, not a person)", 62)}
        if not deep:
            return {**base, **_bucket("deliverable", "Valid domain & mail server", 80)}
        return {**base, **_bucket("deliverable", "Valid mailbox provider", 85)}

    # Deep mode: probe the mailbox (once per domain for catch-all).
    if not info.checked_smtp:
        pr = _smtp_probe(info.mx_hosts, email, mail_from, helo_name, smtp_timeout)
        info.checked_smtp = True
        info.smtp_ok = pr["connected"]
        info.catch_all = pr["catch_all"]
        info._last_rcpt = pr["rcpt"]            # type: ignore[attr-defined]
    rcpt = getattr(info, "_last_rcpt", None)
    base["did_smtp"] = bool(info.smtp_ok)
    base["catch_all"] = bool(info.catch_all)

    if not info.smtp_ok:
        # Port 25 blocked or every server unreachable — fall back to MX verdict.
        if role:
            return {**base, **_bucket("risky", "Role address (mailbox not probed)", 58)}
        return {**base, **_bucket("deliverable",
                                  "Valid mail server (mailbox probe unavailable)", 72)}

    if info.catch_all:
        return {**base, **_bucket("risky",
                                  "Domain accepts all addresses (catch-all) — can't confirm", 55)}
    if rcpt in (250, 251):
        if role:
            return {**base, **_bucket("risky", "Mailbox exists but is a role address", 68)}
        return {**base, **_bucket("deliverable", "Mailbox confirmed by the mail server", 97)}
    if rcpt in (550, 551, 553, 554, 501):
        return {**base, **_bucket("undeliverable",
                                  "Mail server says this mailbox does not exist", 8)}
    if rcpt in (450, 451, 452, 421):
        return {**base, **_bucket("unknown",
                                  "Temporarily deferred (greylisting) — try again later", 50)}
    # any other / no code
    if role:
        return {**base, **_bucket("risky", "Role address — couldn't confirm mailbox", 55)}
    return {**base, **_bucket("unknown", "Mail server gave no clear answer", 50)}
