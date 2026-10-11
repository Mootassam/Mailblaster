"""End-to-end tests for list cleaning + sending, with fake mail servers.

Run:  python -I -X utf8 tests/test_core.py [path\\to\\a\\COPY\\of\\mailblaster.db]
Without a path it builds a small throwaway database. Nothing is ever emailed:
mailer.SMTPSender and verifier.verify_one are replaced by fakes.
"""
import os
import shutil
import smtplib
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

tmp = tempfile.mkdtemp(prefix="mb-test-")
DB = os.path.join(tmp, "mb.db")
if len(sys.argv) > 1:
    shutil.copy2(sys.argv[1], DB)
    for ext in ("-wal", "-shm"):          # WAL mode: recent changes live here
        if os.path.exists(sys.argv[1] + ext):
            shutil.copy2(sys.argv[1] + ext, DB + ext)
os.environ["MB_DB"] = DB

import mailer  # noqa: E402
import server  # noqa: E402
import store  # noqa: E402
import verifier  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    print(("  ok  " if cond else "  XX  ") + name + (f"  ({detail})" if detail else ""))
    if not cond:
        FAILS.append(name)


# ------------------------------------------------------------------ fakes
SENT = []
MODE = {"send": "ok"}


class FakeSender:
    def __init__(self, *a, **k):
        pass

    def connect(self):
        pass

    def quit(self):
        pass

    def verify(self):
        return True

    def send(self, **kw):
        m = MODE["send"]
        if m == "hard_bounce":
            raise mailer.RecipientError("550 5.1.1 user unknown", "hard", 550)
        if m == "relay_reject":   # what Resend answered for a bad Reply-To
            # go through the real classifier to prove it is a sender error
            real = REAL_SENDER.__new__(REAL_SENDER)

            class S:
                def send_message(self, msg):
                    raise smtplib.SMTPDataError(550, b"Invalid `reply_to` field.")

                def rset(self):
                    pass
            real.smtp, real._n = S(), 0
            for k in ("host", "port", "security", "username", "password"):
                setattr(real, k, "")
            real.send(**kw)
        SENT.append(kw["to_email"])
        return "<id@test>"


REAL_SENDER = mailer.SMTPSender
mailer.SMTPSender = FakeSender


def fake_verify(email, **kw):
    time.sleep(0.003)
    h = sum(map(ord, email)) % 4
    res = ["deliverable", "risky", "undeliverable", "unknown"][h]
    return {"email": email, "result": res, "reason": "fake " + res, "score": 50}


verifier.verify_one = fake_verify


def wait_verify(timeout=120):
    t = time.time()
    while time.time() - t < timeout:
        with server._VLOCK:
            if server.VERIFY["status"] != "running":
                return True
        time.sleep(0.05)
    return False


def wait_end(cid, timeout=120):
    t = time.time()
    while time.time() - t < timeout:
        with server._JOBS_LOCK:
            if server.JOBS.get(cid, {}).get("status") != "running":
                return True
        time.sleep(0.05)
    return False


def wait_job(cid, timeout=60):
    t = time.time()
    while time.time() - t < timeout:
        with server._JOBS_LOCK:
            st = server.JOBS.get(cid, {}).get("status")
            br = server.JOBS.get(cid, {}).get("brake")
        if st != "running" or br:
            return st, br
        time.sleep(0.05)
    return "timeout", None


# ------------------------------------------------------------------ setup
store.init()
with store._LOCK, store._conn() as c:
    if not c.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]:
        for i in range(400):
            c.execute("INSERT INTO contacts(email,status,created_at) VALUES(?, 'active', ?)",
                      (f"person{i}@company{i % 37}.com", time.time()))
    checker_err = c.execute("SELECT COUNT(*) FROM contacts WHERE verify_reason LIKE 'checker error:%'").fetchone()[0]
    # fresh slate for the test: forget earlier verification results
    c.execute("UPDATE contacts SET verify_status='' WHERE status='active'")
    c.execute("DELETE FROM accounts")
    c.execute("INSERT INTO accounts(label,host,port,security,username,password,from_name,from_email,"
              "reply_to,daily_limit,active,created_at) VALUES('T','smtp.test',465,'ssl','u','p','T',"
              "'t@test.dev','',100000,1,?)", (time.time(),))
    c.execute("DELETE FROM settings WHERE key LIKE 'sending_window%'")
store.save_settings({"brake_enabled": "1", "auto_verify": "0"})
cl = server.app.test_client()

print("\n1. Startup migration")
check("bogus 'checker error' results were reset for re-checking", checker_err == 0)

print("\n2. Real-time list cleaning")
n_active = store.recipient_count()
r = cl.post("/api/verify/start", data={"scope": "all", "deep": "1", "only_unverified": "1"}).get_json()
check("pass starts", r.get("ok"), r)
r2 = cl.post("/api/verify/start", data={"scope": "all", "deep": "1"}).get_json()
check("a second pass can't start while one runs", not r2.get("ok"), r2.get("error"))
time.sleep(0.4)
s1 = cl.get("/api/verify/status?since=0").get_json()
check("live progress while running", s1["status"] == "running" and 0 < s1["done"] < s1["total"],
      f"{s1['done']}/{s1['total']}")
check("live feed carries per-address results", len(s1["feed"]) > 0 and "email" in s1["feed"][-1])
s1b = cl.get(f"/api/verify/status?since={s1['feed'][-1]['seq']}").get_json()
check("feed only returns new results", all(x["seq"] > s1["feed"][-1]["seq"] for x in s1b["feed"]))
check("speed / time-left reported", s1["rate"] >= 0 and "eta" in s1)
check("pass finishes", wait_verify())
s2 = cl.get("/api/verify/status").get_json()
check("every contact checked", s2["done"] == s2["total"] == n_active, f"{s2['done']}/{s2['total']}/{n_active}")
st = store.verify_stats()
check("undeliverable moved out of sending", st["undeliverable"] >= s2["undeliverable"] and
      store.recipient_count() == n_active - s2["undeliverable"])

print("\n3. Background auto-clean picks up new contacts")
with store._LOCK, store._conn() as c:
    for i in range(25):
        c.execute("INSERT INTO contacts(email,status,created_at) VALUES(?, 'active', ?)",
                  (f"newlead{i}@fresh{i}.ae", time.time()))
targets = store.unverified_active_ids()
check("new contacts are queued for cleaning", len(targets) == 25, len(targets))
server._start_verify(targets, True, "new contacts", auto=True)
wait_verify()
check("new contacts cleaned", not store.unverified_active_ids())

print("\n4. Send only to cleaned emails")
pre = cl.get("/api/verify/precheck?group_ids=&exclude_group_ids=").get_json()
bf = pre["by_filter"]
check("precheck counts every choice", set(bf) == {"all", "safe", "safe_risky"} and bf["safe"] <= bf["safe_risky"] <= bf["all"], bf)
SENT.clear()
r = cl.post("/api/campaign/send", data={"name": "T-safe", "subject": "Hi", "html": "<p>x</p>",
                                        "rate_per_min": "6000", "verify_filter": "safe"}).get_json()
check("launch with 'only confirmed good'", r.get("ok") and r.get("total") == bf["safe"], r)
st_, _ = wait_job(r["campaign_id"])
good = {e for (_, e) in [(0, x["email"]) for x in store.recipients_for(None, vfilter="safe")]}
check("only deliverable contacts were emailed", st_ == "done" and set(SENT) == good and len(SENT) == bf["safe"],
      f"{st_} sent={len(SENT)} expected={bf['safe']}")
camp = store.get_campaign(r["campaign_id"])
check("campaign remembers its filter (resume/follow-ups)", camp.get("verify_filter") == "safe")
r = cl.post("/api/campaign/send", data={"name": "x", "subject": "Hi", "html": "<p>x</p>", "verify_filter": "bogus"}).get_json()
check("unknown filter falls back to everyone", r.get("ok") and r.get("total") == bf["all"], r.get("total"))
cl.post("/api/campaign/control", data={"campaign_id": r["campaign_id"], "action": "stop"})
wait_end(r["campaign_id"])

print("\n5. Sender-side error never bounces contacts")
MODE["send"] = "relay_reject"
store.set_account_fields(store.accounts()[0]["id"], paused_reason="")
before = store.verify_stats()["undeliverable"]
with store._LOCK, store._conn() as c:
    bounced_before = c.execute("SELECT COUNT(*) FROM contacts WHERE status='bounced'").fetchone()[0]
r = cl.post("/api/campaign/send", data={"name": "T-relay", "subject": "Hi", "html": "<p>x</p>",
                                        "rate_per_min": "6000", "verify_filter": "safe_risky"}).get_json()
st_, br = wait_job(r["campaign_id"])
with store._LOCK, store._conn() as c:
    bounced_after = c.execute("SELECT COUNT(*) FROM contacts WHERE status='bounced'").fetchone()[0]
acc = store.accounts()[0]
check("no contact marked bounced", bounced_after == bounced_before, f"{bounced_before}->{bounced_after}")
check("sender auto-paused with the real reason", "reply_to" in (acc.get("paused_reason") or ""), acc.get("paused_reason"))
check("campaign braked instead of burning the list", bool(br), br)
cl.post("/api/campaign/control", data={"campaign_id": r["campaign_id"], "action": "stop"})
wait_end(r["campaign_id"])

print("\n6. Bounce brake trips early")
MODE["send"] = "hard_bounce"
store.set_account_fields(acc["id"], paused_reason="")
r = cl.post("/api/campaign/send", data={"name": "T-bounce", "subject": "Hi", "html": "<p>x</p>",
                                        "rate_per_min": "6000", "verify_filter": "all"}).get_json()
st_, br = wait_job(r["campaign_id"])
n_b = store.send_counts(r["campaign_id"]).get("bounced", 0)
check("brake pauses within the first ~20 bounces", bool(br) and n_b <= 20, f"bounced={n_b} brake={br}")
cl.post("/api/campaign/control", data={"campaign_id": r["campaign_id"], "action": "stop"})
wait_end(r["campaign_id"])

print("\n7. Resume retries failed people without double counting")
MODE["send"] = "ok"
cid = r["campaign_id"]
with store._LOCK, store._conn() as c:
    rows = c.execute("SELECT contact_id FROM sends WHERE campaign_id=? LIMIT 3", (cid,)).fetchall()
    for row in rows:
        c.execute("UPDATE sends SET status='failed' WHERE campaign_id=? AND contact_id=?", (cid, row[0]))
        c.execute("UPDATE contacts SET status='active' WHERE id=?", (row[0],))
store.set_campaign_status(cid, "stopped")
r = cl.post(f"/api/campaign/{cid}/resume-run").get_json()
check("resume starts", r.get("ok"), r)
wait_job(cid, 120)
with store._LOCK, store._conn() as c:
    dup = c.execute("SELECT COUNT(*) FROM (SELECT contact_id FROM sends WHERE campaign_id=? "
                    "GROUP BY contact_id HAVING COUNT(*)>1)", (cid,)).fetchone()[0]
check("no contact counted twice after resume", dup == 0, dup)

print("\n8. Sender form validation")
r = cl.post("/api/accounts", data={"host": "smtp.resend.com", "from_email": "a@b.com", "reply_to": "reply.glotchat.com"})
check("invalid Reply-to rejected", r.status_code == 400)
r = cl.post("/api/accounts", data={"host": "smtp.resend.com", "from_email": "a@b.com", "reply_to": "hello@reply.glotchat.com"})
check("valid Reply-to accepted", r.status_code == 200)

print("\n" + ("ALL PASSED" if not FAILS else f"{len(FAILS)} FAILED: {FAILS}"))
mailer.SMTPSender = REAL_SENDER
sys.exit(1 if FAILS else 0)
