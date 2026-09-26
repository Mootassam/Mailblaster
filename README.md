# MailBlaster

Your own **local cold-email & campaign platform** — a private Mailchimp / Brevo
alternative that runs entirely on your computer. Import contacts into groups, design
an email, and send personalized, tracked, throttled campaigns through **your own**
email accounts. No monthly subscription, no third party holding your list.

## Run

    pip install -r requirements.txt
    python server.py

Then open http://127.0.0.1:5055 (or double-click Start.bat on Windows).

## Features

Deliverability pack (v3)
- **Bounce processing (IMAP)** — each sender's inbox is read (read-only) every few
  minutes. Standard bounce reports (DSN), Gmail/Outlook "Undeliverable" mails and
  X-Failed-Recipients are parsed; hard bounces are removed from sending and put on
  the suppression list, soft bounces are counted (removed after N). SMTP-time
  rejections (550 user unknown) are caught instantly too.
- **Spam complaints** (ARF feedback loops) unsubscribe the contact automatically.
- **Reply detection + unified inbox** — replies are matched to their campaign by
  Message-ID (or sender address), auto-labeled (Interested / Meeting / Not
  interested / Unsubscribe request), stop that contact's follow-ups, and can be
  answered from inside MailBlaster in the same thread. Out-of-office replies are
  separated. Personal mail is ignored and never stored.
- **Sender warm-up** — per sender: start at N/day and grow X% per day up to the
  daily limit; enforced automatically, with a visual ramp.
- **Safety brakes** — a campaign auto-pauses when the bounce rate, failure rate,
  consecutive failures, spam complaints or unsubscribe rate cross your limits.
  A sender that fails 5 times in a row is auto-paused and the campaign continues on
  the others. When every sender hits its daily limit, the campaign waits and
  continues automatically the next day.
- **Crash-safe resume** — an interrupted/stopped campaign resumes with only the
  people not yet emailed.

Contacts & groups
- Groups with colors: create, rename, delete (keep contacts, or delete them too).
- Import a CSV straight into an existing or new group (auto-detects `,` `;` tab).
- Select contacts per page or "select all N matching" (Gmail-style), then bulk
  add to group, remove from group, unsubscribe or delete. "Delete all" with
  type-to-confirm. Unsubscribed/bounced addresses stay suppressed even after
  deleting and re-importing.
- Campaigns target one or more groups and can **exclude** groups; contacts in
  several groups get the email once.

Sending
- Multiple sender accounts with rotation + per-account daily limits
  (Gmail, Outlook, Zoho, SendGrid, Mailgun, Amazon SES, Brevo, custom SMTP).
- Throttling + random delay, sending window, scheduling, concurrent campaigns,
  live progress with pause/resume/stop.
- A/B subject tests, follow-up sequences (non-openers / openers / everyone).
- Proper Message-ID + Date headers, List-Unsubscribe with RFC 8058 one-click
  (when a public https tracking URL is set). The unsubscribe page asks for a
  click, so email link-scanners can't unsubscribe people by accident.

Content & reporting
- Template gallery, merge tags with fallbacks ({{first_name|there}},
  {{data.company}}), live desktop/mobile preview, spam-score checker, test sends.
- Dashboard with 14-day chart; per-campaign report: delivered, opens, clicks,
  replies, bounces, unsubscribes, A/B winner, follow-ups, top links, activity.
- Deliverability page: 30-day health, brake settings, bounce log, suppression list
  manager, warm-up overview, domain check (MX / SPF / DMARC).

## Setting up inbox sync
Edit a sender → "Inbox sync (IMAP)". Gmail, Outlook, Yahoo and Zoho are auto-filled.
Gmail/Outlook need IMAP enabled and an app password. Add `[Gmail]/Spam` to the
folders if bounces land in spam.

## Deliverability tips
- Only email people who opted in or have a legitimate reason to hear from you.
- Warm up new senders over 2–4 weeks; keep bounce rate < 2%, complaints < 0.1%.
- Set up SPF, DKIM and DMARC on your sending domain.
- Open/click tracking needs recipients to reach this app: expose it with a tunnel
  (ngrok, Cloudflare Tunnel) and paste the public https URL in Settings.

Everything is stored locally in mailblaster.db.
