"""
Peaks and Valleys Construction — Badge Generator Webhook
Deploy on Railway / Render / DigitalOcean App Platform

ENV VARS REQUIRED:
  SMTP_HOST      e.g. smtp.gmail.com
  SMTP_PORT      e.g. 587
  SMTP_USER      e.g. office@peaksroofs.com
  SMTP_PASS      App password (not your login password)
  OFFICE_EMAIL   office@peaksroofs.com
  SECRET_KEY     Any random string — must match GHL webhook header
"""

import os, io, re, requests, tempfile, smtplib, traceback
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from flask import Flask, request, jsonify
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import inch
from reportlab.lib.colors import HexColor, white, Color
from reportlab.lib.utils import ImageReader
from PIL import Image
import math, random

app = Flask(__name__)

# ── Brand colors ──────────────────────────────────────────────────────────
GOLD       = HexColor("#C8912A")
GOLD_DARK  = HexColor("#8B6010")
DARK_BG    = HexColor("#111111")
FOOTER_BG  = HexColor("#0B0B0B")
DARK_LOGO  = HexColor("#1a1100")
LIGHT_TXT  = HexColor("#BBBBBB")
MID_TXT    = HexColor("#777777")
DIM_TXT    = HexColor("#555555")
DARK_SVC   = HexColor("#3d3d3d")

LOGO_PATH  = os.path.join(os.path.dirname(__file__), "logo.png")


# ═══════════════════════════════════════════════════════════════════════════
# PDF BADGE GENERATOR
# ═══════════════════════════════════════════════════════════════════════════

def rr(c, x, y, w, h, r, fill_color=None, stroke_color=None, sw=0):
    p = c.beginPath()
    p.moveTo(x+r, y)
    p.lineTo(x+w-r, y)
    p.arcTo(x+w-2*r, y, x+w, y+2*r, -90, 90)
    p.lineTo(x+w, y+h-r)
    p.arcTo(x+w-2*r, y+h-2*r, x+w, y+h, 0, 90)
    p.lineTo(x+r, y+h)
    p.arcTo(x, y+h-2*r, x+2*r, y+h, 90, 90)
    p.lineTo(x, y+r)
    p.arcTo(x, y, x+2*r, y+2*r, 180, 90)
    p.close()
    if fill_color:
        c.setFillColor(fill_color)
    if stroke_color:
        c.setStrokeColor(stroke_color)
        c.setLineWidth(sw)
    c.drawPath(p, fill=1 if fill_color else 0, stroke=1 if stroke_color else 0)

def draw_rect(c, x, y, w, h, fill=None, stroke=None, sw=0.5):
    if fill:   c.setFillColor(fill)
    if stroke: c.setStrokeColor(stroke); c.setLineWidth(sw)
    c.rect(x, y, w, h, fill=1 if fill else 0, stroke=1 if stroke else 0)

def txt(c, text, x, y, font, size, color, anchor="left"):
    c.setFont(font, size)
    c.setFillColor(color)
    if anchor == "center": c.drawCentredString(x, y, text)
    elif anchor == "right": c.drawRightString(x, y, text)
    else: c.drawString(x, y, text)

def circle_clip(c, cx, cy, r):
    p = c.beginPath()
    p.circle(cx, cy, r)
    c.clipPath(p, stroke=0)

def qr_corner(c, x, y, size):
    s = size
    draw_rect(c, x, y, s, s, fill=DARK_BG)
    i1 = s * 0.12
    draw_rect(c, x+i1, y+i1, s-2*i1, s-2*i1, fill=white)
    i2 = s * 0.28
    draw_rect(c, x+i2, y+i2, s-2*i2, s-2*i2, fill=DARK_BG)

def qr_data_dots(c, bx, by, bw, bh):
    dot  = 0.018 * inch
    gap  = 0.011 * inch
    step = dot + gap
    margin = 0.12 * inch
    sx, sy = bx + margin, by + margin
    ew, eh = bw - 2*margin, bh - 2*margin
    random.seed(99)
    c.setFillColor(DARK_BG)
    nx = int(ew / step)
    ny = int(eh / step)
    for row in range(ny):
        for col in range(nx):
            if row < 3 and col < 3: continue
            if row < 3 and col >= nx-3: continue
            if row >= ny-3 and col < 3: continue
            if random.random() > 0.45:
                c.rect(sx+col*step, sy+row*step, dot, dot, fill=1, stroke=0)


def generate_badge(name, title, phone, email, photo_bytes=None):
    W = 3.375 * inch
    H = 2.125 * inch
    BORDER_R   = 6
    GOLD_BAR_H = 0.44 * inch
    FOOTER_H   = 0.53 * inch
    BODY_Y     = FOOTER_H
    BODY_H     = H - GOLD_BAR_H - FOOTER_H
    PAD        = 0.09 * inch
    PHOTO_W    = 0.72 * inch
    PHOTO_H    = BODY_H - 2*PAD
    PHOTO_X    = PAD
    PHOTO_Y    = BODY_Y + PAD

    buf = io.BytesIO()
    c = Canvas(buf, pagesize=(W, H))

    # Card + border
    rr(c, 0, 0, W, H, BORDER_R, fill_color=DARK_BG)
    rr(c, 0, 0, W, H, BORDER_R, stroke_color=GOLD, sw=1.8)
    c.setStrokeAlpha(0.22)
    rr(c, 3.5, 3.5, W-7, H-7, BORDER_R-2, stroke_color=GOLD, sw=0.4)
    c.setStrokeAlpha(1)

    # Gold top bar
    gold_bar_y = H - GOLD_BAR_H
    rr(c, 0, gold_bar_y, W, GOLD_BAR_H, BORDER_R, fill_color=GOLD)
    draw_rect(c, 0, gold_bar_y, W, BORDER_R, fill=GOLD)
    c.setStrokeAlpha(0.6)
    c.setStrokeColor(GOLD_DARK); c.setLineWidth(1.0)
    c.line(0, gold_bar_y, W, gold_bar_y)
    c.setStrokeAlpha(1)

    # Logo
    logo_r  = 0.185 * inch
    logo_cx = 0.265 * inch
    logo_cy = H - GOLD_BAR_H / 2
    c.circle(logo_cx, logo_cy, logo_r, fill=1, stroke=0)
    c.setFillColor(DARK_LOGO); c.circle(logo_cx, logo_cy, logo_r, fill=1, stroke=0)
    c.saveState()
    circle_clip(c, logo_cx, logo_cy, logo_r)
    c.drawImage(LOGO_PATH, logo_cx-logo_r, logo_cy-logo_r,
                width=logo_r*2.1, height=logo_r*2.1, mask='auto')
    c.restoreState()

    # Company name
    bar_cx = W/2 + 0.04*inch
    bar_cy = H - GOLD_BAR_H/2
    txt(c, "PEAKS AND VALLEYS", bar_cx, bar_cy+0.038*inch,
        "Helvetica-Bold", 7.8, DARK_LOGO, anchor="center")
    txt(c, "CONSTRUCTION", bar_cx, bar_cy-0.055*inch,
        "Helvetica", 6, HexColor("#3a2500"), anchor="center")

    # Footer
    rr(c, 0, 0, W, FOOTER_H, BORDER_R, fill_color=FOOTER_BG)
    draw_rect(c, 0, FOOTER_H-BORDER_R, W, BORDER_R, fill=FOOTER_BG)
    c.setStrokeColor(GOLD); c.setLineWidth(0.8); c.setStrokeAlpha(0.5)
    c.line(0, FOOTER_H, W, FOOTER_H)
    c.setStrokeAlpha(1)
    txt(c, "FORGED IN THE VALLEYS.  BUILT FOR THE PEAKS.",
        W/2, FOOTER_H-0.195*inch, "Helvetica-Oblique", 5.5, GOLD, anchor="center")
    txt(c, "ROOFING  \u00b7  SIDING  \u00b7  GUTTERS  \u00b7  STORM DAMAGE REPAIR",
        W/2, FOOTER_H-0.33*inch, "Helvetica", 4.2, DARK_SVC, anchor="center")

    # Photo area
    rr(c, PHOTO_X, PHOTO_Y, PHOTO_W, PHOTO_H, 3,
       fill_color=HexColor("#1c1c1c"), stroke_color=GOLD, sw=1.0)

    if photo_bytes:
        try:
            pil = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
            # crop to portrait aspect
            pw, ph = pil.size
            target_ratio = PHOTO_W / PHOTO_H
            actual_ratio = pw / ph
            if actual_ratio > target_ratio:
                new_w = int(ph * target_ratio)
                left  = (pw - new_w) // 2
                pil   = pil.crop((left, 0, left+new_w, ph))
            else:
                new_h = int(pw / target_ratio)
                top   = (ph - new_h) // 2
                pil   = pil.crop((0, top, pw, top+new_h))
            img_buf = io.BytesIO()
            pil.save(img_buf, format="PNG")
            img_buf.seek(0)
            ir = ImageReader(img_buf)
            # clip to rounded rect
            c.saveState()
            p2 = c.beginPath()
            p2.moveTo(PHOTO_X+3, PHOTO_Y)
            p2.lineTo(PHOTO_X+PHOTO_W-3, PHOTO_Y)
            p2.arcTo(PHOTO_X+PHOTO_W-6, PHOTO_Y, PHOTO_X+PHOTO_W, PHOTO_Y+6, -90, 90)
            p2.lineTo(PHOTO_X+PHOTO_W, PHOTO_Y+PHOTO_H-3)
            p2.arcTo(PHOTO_X+PHOTO_W-6, PHOTO_Y+PHOTO_H-6, PHOTO_X+PHOTO_W, PHOTO_Y+PHOTO_H, 0, 90)
            p2.lineTo(PHOTO_X+3, PHOTO_Y+PHOTO_H)
            p2.arcTo(PHOTO_X, PHOTO_Y+PHOTO_H-6, PHOTO_X+6, PHOTO_Y+PHOTO_H, 90, 90)
            p2.lineTo(PHOTO_X, PHOTO_Y+3)
            p2.arcTo(PHOTO_X, PHOTO_Y, PHOTO_X+6, PHOTO_Y+6, 180, 90)
            p2.close()
            c.clipPath(p2, stroke=0)
            c.drawImage(ir, PHOTO_X, PHOTO_Y, width=PHOTO_W, height=PHOTO_H)
            c.restoreState()
        except Exception:
            pass  # fallback to placeholder if photo fails
    else:
        icon_cx = PHOTO_X + PHOTO_W/2
        icon_cy = PHOTO_Y + PHOTO_H/2 + 0.02*inch
        c.setFillColor(HexColor("#2a2a2a"))
        c.circle(icon_cx, icon_cy+0.02*inch, 0.055*inch, fill=1, stroke=0)
        c.setFillColor(HexColor("#3a3a3a"))
        c.circle(icon_cx, icon_cy+0.02*inch, 0.03*inch, fill=1, stroke=0)
        txt(c, "PHOTO", icon_cx, PHOTO_Y+0.1*inch, "Helvetica", 4.5, DIM_TXT, anchor="center")

    # Content column
    COL_X   = PHOTO_X + PHOTO_W + 0.1*inch
    COL_TOP = BODY_Y + BODY_H - PAD - 0.02*inch
    NAME_Y  = COL_TOP - 0.11*inch

    # Truncate name if too long
    display_name = name.upper()[:22]
    txt(c, display_name, COL_X, NAME_Y, "Helvetica-Bold", 13, white)

    TITLE_Y = NAME_Y - 0.115*inch
    display_title = title.upper()[:28]
    txt(c, display_title, COL_X, TITLE_Y, "Helvetica", 5.5, GOLD)

    rule_y = TITLE_Y - 0.055*inch
    c.setStrokeColor(GOLD); c.setLineWidth(0.5); c.setStrokeAlpha(0.4)
    c.line(COL_X, rule_y, W-0.63*inch, rule_y)
    c.setStrokeAlpha(1)

    PHONE_Y = rule_y - 0.08*inch
    txt(c, phone, COL_X, PHONE_Y, "Helvetica", 5.8, LIGHT_TXT)

    EMAIL_Y = PHONE_Y - 0.075*inch
    display_email = email[:42]
    txt(c, display_email, COL_X, EMAIL_Y, "Helvetica", 4.6, MID_TXT)

    # Pill
    pill_y = EMAIL_Y - 0.11*inch
    pill_w = 0.82*inch
    pill_h = 0.1*inch
    c.saveState()
    c.setFillColor(GOLD); c.setFillAlpha(0.12)
    rr(c, COL_X, pill_y, pill_w, pill_h, pill_h/2, fill_color=GOLD)
    c.restoreState()
    c.setStrokeColor(GOLD); c.setLineWidth(0.5)
    rr(c, COL_X, pill_y, pill_w, pill_h, pill_h/2, stroke_color=GOLD, sw=0.5)
    txt(c, "PEAKS EXTERIOR PRO", COL_X+pill_w/2, pill_y+0.028*inch,
        "Helvetica", 4.0, GOLD, anchor="center")

    serving_y = pill_y - 0.07*inch
    txt(c, "SERVING OREGON & WASHINGTON", COL_X, serving_y, "Helvetica", 4.0, DIM_TXT)

    # QR
    QR_W  = 0.58 * inch
    QR_H  = PHOTO_H
    QR_X  = W - PAD - QR_W
    QR_Y  = PHOTO_Y
    rr(c, QR_X, QR_Y, QR_W, QR_H, 3, fill_color=white)
    cs = 0.094 * inch
    qr_corner(c, QR_X+0.028*inch, QR_Y+QR_H-0.028*inch-cs, cs)
    qr_corner(c, QR_X+QR_W-0.028*inch-cs, QR_Y+QR_H-0.028*inch-cs, cs)
    qr_corner(c, QR_X+0.028*inch, QR_Y+0.028*inch, cs)
    qr_data_dots(c, QR_X, QR_Y, QR_W, QR_H)
    txt(c, "SCAN TO CONNECT", QR_X+QR_W/2, QR_Y-0.045*inch,
        "Helvetica", 3.5, DIM_TXT, anchor="center")

    # Divider
    c.setStrokeColor(GOLD); c.setLineWidth(0.5); c.setStrokeAlpha(0.3)
    c.line(PAD, FOOTER_H+0.005*inch, W-PAD, FOOTER_H+0.005*inch)
    c.setStrokeAlpha(1)

    c.save()
    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════════════════
# EMAIL SENDER
# ═══════════════════════════════════════════════════════════════════════════

def send_badge_email(to_email, name, pdf_bytes):
    smtp_host  = os.environ["SMTP_HOST"]
    smtp_port  = int(os.environ.get("SMTP_PORT", 587))
    smtp_user  = os.environ["SMTP_USER"]
    smtp_pass  = os.environ["SMTP_PASS"]
    office     = os.environ.get("OFFICE_EMAIL", "office@peaksroofs.com")

    first_name = name.split()[0].title() if name else "Team"
    recipients = list({to_email, office})  # dedupe in case same

    msg = MIMEMultipart()
    msg["From"]    = f"Peaks and Valleys Construction <{smtp_user}>"
    msg["To"]      = to_email
    msg["CC"]      = office
    msg["Subject"] = f"ID Badge Ready — {name.title()}"

    body = f"""Hi {first_name},

Your Peaks and Valleys Construction ID badge is attached and print-ready.

Print specs:
  • Size: 3.375" x 2.125"  (CR80 standard badge)
  • Send to any badge printer or office print shop as-is

Questions? Reply to this email or reach us at {office}.

— Peaks and Valleys Construction
   FORGED IN THE VALLEYS. BUILT FOR THE PEAKS.
"""
    msg.attach(MIMEText(body, "plain"))

    part = MIMEBase("application", "pdf")
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    part.add_header("Content-Disposition", "attachment",
                    filename=f"PVC_Badge_{safe_name}.pdf")
    msg.attach(part)

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, recipients, msg.as_string())


# ═══════════════════════════════════════════════════════════════════════════
# WEBHOOK ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "PVC Badge Generator"})


@app.route("/badge", methods=["POST"])
def badge_webhook():
    # Optional secret key check
    secret = os.environ.get("SECRET_KEY", "")
    if secret:
        incoming = request.headers.get("X-PVC-Secret", "")
        if incoming != secret:
            return jsonify({"error": "Unauthorized"}), 401

    try:
        # ── Parse form data (GHL sends multipart or JSON) ──────────────────
        if request.content_type and "multipart" in request.content_type:
            data  = request.form
            photo = request.files.get("headshot")
            photo_bytes = photo.read() if photo else None
        else:
            data  = request.get_json(force=True) or {}
            photo_bytes = None
            # GHL may send photo as a URL in JSON payload
            photo_url = data.get("headshot_url") or data.get("headshot")
            if photo_url and photo_url.startswith("http"):
                r = requests.get(photo_url, timeout=15)
                if r.status_code == 200:
                    photo_bytes = r.content

        name  = (data.get("full_name")  or data.get("name")  or "").strip()
        title = (data.get("job_title")  or data.get("title") or "").strip()
        phone = (data.get("phone")      or "").strip()
        email = (data.get("email")      or "").strip()

        if not name or not email:
            return jsonify({"error": "full_name and email are required"}), 400

        # ── Generate PDF ────────────────────────────────────────────────────
        pdf_bytes = generate_badge(name, title, phone, email, photo_bytes)

        # ── Send email ──────────────────────────────────────────────────────
        send_badge_email(email, name, pdf_bytes)

        return jsonify({
            "success": True,
            "message": f"Badge generated and emailed to {email}"
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
