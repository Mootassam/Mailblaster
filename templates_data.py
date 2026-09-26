"""Built-in cold-email + newsletter templates shown in the UI gallery."""

TEMPLATES = [
    {
        "id": "cold-intro",
        "name": "Cold intro (short)",
        "category": "Cold email",
        "subject": "Quick question, {{first_name|there}}",
        "html": """<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;line-height:1.6">
<p>Hi {{first_name|there}},</p>
<p>I'll keep this short — I help companies like {{data.company|yours}} [achieve a specific result].</p>
<p>Would it be crazy to grab 10 minutes this week to see if it's a fit?</p>
<p>Best,<br>Your Name</p>
<p style="font-size:12px;color:#888">Not interested? {{unsubscribe}}</p>
</div>""",
        "text": "Hi {{first_name|there}}, I help companies like {{data.company|yours}}... Open to a quick 10-min chat?",
    },
    {
        "id": "cold-value",
        "name": "Cold email (value + CTA)",
        "category": "Cold email",
        "subject": "An idea for {{data.company|your team}}",
        "html": """<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;line-height:1.6">
<p>Hey {{first_name|there}},</p>
<p>Noticed {{data.company|your company}} is [doing X]. We recently helped [similar company]
achieve [result] in [timeframe].</p>
<p>Here's how it could work for you:</p>
<ul><li>Benefit one</li><li>Benefit two</li><li>Benefit three</li></ul>
<p><a href="https://your-link.com" style="background:#4f46e5;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none">Book a quick call</a></p>
<p>— Your Name</p>
<p style="font-size:12px;color:#888">{{unsubscribe}}</p>
</div>""",
        "text": "Hey {{first_name|there}}, an idea for {{data.company|your team}}...",
    },
    {
        "id": "followup",
        "name": "Follow-up / bump",
        "category": "Cold email",
        "subject": "Re: Quick question, {{first_name|there}}",
        "html": """<div style="font-family:Arial,sans-serif;font-size:15px;color:#222;line-height:1.6">
<p>Hi {{first_name|there}},</p>
<p>Just floating this back to the top of your inbox — did you get a chance to think it over?</p>
<p>Happy to share a couple of quick examples if useful.</p>
<p>Cheers,<br>Your Name</p>
<p style="font-size:12px;color:#888">{{unsubscribe}}</p>
</div>""",
        "text": "Hi {{first_name|there}}, just floating this back up — any thoughts?",
    },
    {
        "id": "newsletter",
        "name": "Newsletter",
        "category": "Newsletter",
        "subject": "{{first_name|Hi}}, here's what's new",
        "html": """<div style="max-width:600px;margin:auto;font-family:Arial,sans-serif;color:#222">
<div style="background:#4f46e5;color:#fff;padding:22px;border-radius:12px 12px 0 0">
<h1 style="margin:0;font-size:22px">Your Brand</h1></div>
<div style="padding:22px;border:1px solid #eee;border-top:none;border-radius:0 0 12px 12px;line-height:1.6">
<p>Hi {{first_name|there}},</p>
<h2 style="font-size:18px">Headline of the month</h2>
<p>Your update goes here…</p>
<p><a href="https://your-link.com" style="background:#4f46e5;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none">Read more</a></p>
<hr style="border:none;border-top:1px solid #eee;margin:20px 0">
<p style="font-size:12px;color:#888">You're receiving this because you subscribed. {{unsubscribe}}</p>
</div></div>""",
        "text": "Hi {{first_name|there}}, here's what's new...",
    },
    {
        "id": "promo",
        "name": "Promo / offer",
        "category": "Promotion",
        "subject": "A little something for you, {{first_name|friend}}",
        "html": """<div style="max-width:600px;margin:auto;font-family:Arial,sans-serif;text-align:center;color:#222">
<div style="padding:30px;border:1px solid #eee;border-radius:12px">
<h1 style="color:#4f46e5">Special offer inside</h1>
<p>Hi {{first_name|there}}, we've got something we think you'll love.</p>
<p style="font-size:30px;font-weight:800;margin:10px 0">20% OFF</p>
<p><a href="https://your-link.com" style="background:#4f46e5;color:#fff;padding:12px 26px;border-radius:8px;text-decoration:none;font-weight:700">Shop now</a></p>
<p style="font-size:12px;color:#888;margin-top:24px">{{unsubscribe}}</p>
</div></div>""",
        "text": "Hi {{first_name|there}}, 20% off just for you...",
    },
    {
        "id": "blank",
        "name": "Blank",
        "category": "Basic",
        "subject": "",
        "html": "<div style=\"font-family:Arial,sans-serif;font-size:15px;color:#222;line-height:1.6\">\n<p>Hi {{first_name|there}},</p>\n<p>Write your message here…</p>\n<p>{{unsubscribe}}</p>\n</div>",
        "text": "Hi {{first_name|there}},\n\nWrite your message here…",
    },
]
