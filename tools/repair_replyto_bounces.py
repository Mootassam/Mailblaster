"""One-off repair (2026-10-11): undo the fake "bounces" caused by an invalid Reply-to.

Resend refused every email with "Invalid `reply_to` field" and MailBlaster (before the fix)
recorded each refusal as a hard bounce: contact marked bounced + email on the do-not-email list.
None of those emails were sent. This restores exactly those contacts and nothing else.

Close MailBlaster first. A backup copy of the database is made before anything changes.
"""
import os
import shutil
import sqlite3
import time

DB = os.path.expandvars(r"%LOCALAPPDATA%\MailBlaster\mailblaster.db")
MARK = "%Invalid `reply_to`%"

backup = DB.replace(".db", time.strftime("-backup-%Y%m%d-%H%M%S.db"))
shutil.copy2(DB, backup)
print("Backup:", backup)

c = sqlite3.connect(DB)
emails = [r[0] for r in c.execute("SELECT DISTINCT email FROM bounces WHERE reason LIKE ?", (MARK,))]
camps = [r[0] for r in c.execute("SELECT DISTINCT campaign_id FROM bounces WHERE reason LIKE ?", (MARK,))]
print("Contacts wrongly marked bounced:", len(emails))

c.execute("DELETE FROM bounces WHERE reason LIKE ?", (MARK,))
unsup = 0
for e in emails:  # keep anyone who also has a genuine bounce/complaint
    if not c.execute("SELECT 1 FROM bounces WHERE email=? AND kind IN ('hard','complaint')", (e,)).fetchone():
        unsup += c.execute("DELETE FROM suppression WHERE email=? AND reason='bounce'", (e,)).rowcount
restored = c.execute("UPDATE contacts SET status='active', status_reason='' WHERE status_reason LIKE ?",
                     (MARK,)).rowcount
cleared = c.execute("DELETE FROM sends WHERE error LIKE ?", (MARK,)).rowcount
for cid in camps:
    c.execute("UPDATE campaigns SET bounced=(SELECT count(*) FROM bounces WHERE campaign_id=?) WHERE id=?",
              (cid, cid))
fixed = c.execute("UPDATE accounts SET reply_to='' WHERE reply_to='reply.glotchat.com'").rowcount
c.commit()

print("Removed from do-not-email list:", unsup)
print("Contacts restored to active:", restored)
print("Unsent attempts cleared (they will be sent when you resume):", cleared)
print("Senders with the invalid Reply-to cleared:", fixed)
print("Done. Start MailBlaster again.")
