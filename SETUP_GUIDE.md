# PVC Badge Generator — Complete Setup Guide
## From zero to live in about 30 minutes

---

## WHAT YOU'RE BUILDING

```
Employee fills GHL form  →  form submits to your server  →  badge PDF generated  →  emailed to employee + office@peaksroofs.com
```

---

## STEP 1 — Upload files to GitHub (5 min)

You need a free GitHub account. Go to github.com → New Repository → name it `pvc-badge-server` → Public.

Upload these 3 files:
  • app.py
  • requirements.txt
  • Procfile

Also upload your logo PNG and rename it exactly:  **logo.png**

---

## STEP 2 — Deploy on Railway (10 min, free tier works)

1. Go to **railway.app** → sign up with GitHub
2. Click **New Project** → **Deploy from GitHub repo** → select `pvc-badge-server`
3. Railway auto-detects Python and deploys. Wait ~2 minutes.
4. Click your service → **Settings** → **Generate Domain**
   → You'll get a URL like: `https://pvc-badge-server-production.up.railway.app`
   → Your webhook endpoint is: `https://pvc-badge-server-production.up.railway.app/badge`

### Set Environment Variables in Railway
Go to your service → **Variables** tab → add these one by one:

| Variable     | Value                          |
|--------------|--------------------------------|
| SMTP_HOST    | smtp.gmail.com                 |
| SMTP_PORT    | 587                            |
| SMTP_USER    | office@peaksroofs.com          |
| SMTP_PASS    | (your Gmail app password — see below) |
| OFFICE_EMAIL | office@peaksroofs.com          |
| SECRET_KEY   | peaksvalley2024secure          |

### Getting a Gmail App Password
1. Go to myaccount.google.com → Security
2. Turn on 2-Step Verification if not already on
3. Search for "App passwords" → Create one named "Badge Server"
4. Copy the 16-character password → paste into SMTP_PASS

> Using a different email host? Change SMTP_HOST to your provider's SMTP address.

---

## STEP 3 — Test the server (2 min)

Open a browser and visit:
`https://YOUR-RAILWAY-URL.up.railway.app/health`

You should see: `{"status": "ok", "service": "PVC Badge Generator"}`

If you see that, your server is live. ✓

---

## STEP 4 — Set up the GHL page (10 min)

### In GoHighLevel:
1. Go to **Sites** → **Funnels** (or Websites) → Create new page
   → Name it "Employee Badge Request" or similar
2. Open the page builder
3. Add a new section → drag in a **Custom Code** element
4. Paste the entire contents of **ghl_form_embed.html** into the code box
5. Find this line near the bottom of the code:
   ```
   var WEBHOOK_URL = "YOUR_WEBHOOK_URL/badge";
   ```
   Replace `YOUR_WEBHOOK_URL` with your Railway URL, e.g.:
   ```
   var WEBHOOK_URL = "https://pvc-badge-server-production.up.railway.app/badge";
   ```
6. Save and publish the page

### Optional: Add your logo to the form header
Find this line in the HTML:
```html
<img src="https://i.imgur.com/placeholder.png" .../>
```
Replace the URL with a direct link to your logo image.
Easiest way: upload your logo to your GHL Media Library → copy the URL → paste it in.

---

## STEP 5 — GHL Copilot Prompt (copy and paste this)

If you use GHL's AI Copilot to help set up the workflow, paste this prompt:

---
**COPILOT PROMPT — COPY EVERYTHING BELOW THIS LINE:**

I need to set up a custom HTML form page for employee ID badge requests. Here is what I need:

1. Create a new funnel page called "Employee Badge Request"
2. The page uses a single Custom Code element — I will paste the HTML/CSS/JS code myself
3. The form collects: full name, job title, phone number, email address, and a headshot photo upload
4. When submitted, the form sends a multipart POST request to an external webhook URL I will provide
5. On success, show a confirmation message that the badge has been emailed
6. The page should not use any GHL native form elements — only the custom HTML block
7. Make the page publicly accessible without login
8. Set the page meta title to "Request Your ID Badge — Peaks and Valleys Construction"

Please create this page structure and confirm when ready for me to add the custom code.

---

---

## STEP 6 — Share the link with your team

Once the GHL page is published, copy the page URL and share it with:
- New hires during onboarding
- Existing team members who need a badge
- Anyone with access to your internal GHL links

---

## TROUBLESHOOTING

**Badge email not arriving?**
- Check spam folder
- Confirm SMTP_PASS is the App Password, not your Google login password
- Visit Railway dashboard → your service → Logs to see error details

**Photo not showing on badge?**
- Make sure the photo is a JPG, PNG, or WEBP
- Square photos work best (the server crops automatically)
- Max recommended size: 10MB

**Server returning 401 Unauthorized?**
- The form's SECRET_KEY header must match your Railway SECRET_KEY env var
- The current form code doesn't send this header by default (no secret key needed for the form)
- If you added SECRET_KEY in Railway, either remove it or add the header in the form JS

**Want to update the badge design later?**
- Edit app.py → push to GitHub → Railway auto-redeploys in ~90 seconds

---

## COST SUMMARY

| Service  | Cost           |
|----------|---------------|
| Railway  | Free tier (500hr/mo) or $5/mo Hobby plan |
| GitHub   | Free          |
| Gmail SMTP | Free (with app password) |
| **Total** | **$0–5/month** |

---

## FILES IN THIS PACKAGE

| File | Purpose |
|------|---------|
| app.py | The badge server — handles webhook, generates PDF, sends email |
| requirements.txt | Python packages Railway will install |
| Procfile | Tells Railway how to start the server |
| ghl_form_embed.html | Paste this into GHL Custom Code element |
| logo.png | YOUR LOGO — rename your logo file to this and upload to GitHub |
| SETUP_GUIDE.md | This file |
