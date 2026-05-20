"""
Peaks and Valleys Construction — Badge Generator Webhook
No Pillow dependency — pure Flask + ReportLab only.

ENV VARS REQUIRED:
  SMTP_HOST      e.g. smtp.gmail.com
  SMTP_PORT      587
  SMTP_USER      office@peaksroofs.com
  SMTP_PASS      Gmail App Password
  OFFICE_EMAIL   office@peaksroofs.com
  SECRET_KEY     Any random string (optional)
"""

import os, io, re, requests, smtplib, traceback, random
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from flask import Flask, request, jsonify
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import inch
from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader

app = Flask(__name__)

GOLD      = HexColor("#C8912A")
GOLD_DARK = HexColor("#8B6010")
DARK_BG   = HexColor("#111111")
FOOTER_BG = HexColor("#0B0B0B")
DARK_LOGO = HexColor("#1a1100")
LIGHT_TXT = HexColor("#BBBBBB")
MID_TXT   = HexColor("#777777")
DIM_TXT   = HexColor("#555555")
DARK_SVC  = HexColor("#3d3d3d")

LOGO_PATH = os.path.join(os.path.dirname(__file__), "logo.png")


# ── Drawing helpers ────────────────────────────────────────────────────────

def rr(c, x, y, w, h, r, fill_color=None, stroke_color=None, sw=0):
    p = c.beginPath()
    p.moveTo(x+r, y);       p.lineTo(x+w-r, y)
    p.arcTo(x+w-2*r, y,     x+w, y+2*r,     -90, 90)
    p.lineTo(x+w, y+h-r)
    p.arcTo(x+w-2*r, y+h-2*r, x+w, y+h,     0,   90)
    p.lineTo(x+r, y+h)
    p.arcTo(x, y+h-2*r,     x+2*r, y+h,     90,  90)
    p.lineTo(x, y+r)
    p.arcTo(x, y,            x+2*r, y+2*r,   180, 90)
    p.close()
    if fill_color:   c.setFillColor(fill_color)
    if stroke_color: c.setStrokeColor(stroke_color); c.setLineWidth(sw)
    c.drawPath(p, fill=1 if fill_color else 0, stroke=1 if stroke_color else 0)

def drect(c, x, y, w, h, fill=None, stroke=None, sw=0.5):
    if fill:   c.setFillColor(fill)
    if stroke: c.setStrokeColor(stroke); c.setLineWidth(sw)
    c.rect(x, y, w, h, fill=1 if fill else 0, stroke=1 if stroke else 0)

def txt(c, text, x, y, font, size, color, anchor="left"):
    c.setFont(font, size); c.setFillColor(color)
    if   anchor == "center": c.drawCentredString(x, y, text)
    elif anchor == "right":  c.drawRightString(x, y, text)
    else:                    c.drawString(x, y, text)

def qr_corner(c, x, y, s):
    drect(c, x, y, s, s, fill=DARK_BG)
    i1 = s*0.12; drect(c, x+i1, y+i1, s-2*i1, s-2*i1, fill=white)
    i2 = s*0.28; drect(c, x+i2, y+i2, s-2*i2, s-2*i2, fill=DARK_BG)

def qr_dots(c, bx, by, bw, bh):
    dot=0.018*inch; gap=0.011*inch; step=dot+gap; margin=0.12*inch
    sx,sy=bx+margin,by+margin; ew,eh=bw-2*margin,bh-2*margin
    random.seed(99); c.setFillColor(DARK_BG)
    nx,ny=int(ew/step),int(eh/step)
    for row in range(ny):
        for col in range(nx):
            if row<3 and col<3: continue
            if row<3 and col>=nx-3: continue
            if row>=ny-3 and col<3: continue
            if random.random()>0.45:
                c.rect(sx+col*step, sy+row*step, dot, dot, fill=1, stroke=0)


# ── Badge generator ────────────────────────────────────────────────────────

def generate_badge(name, title, phone, email, photo_bytes=None):
    W=3.375*inch; H=2.125*inch
    BR=6; GBH=0.44*inch; FH=0.53*inch
    BY=FH; BH=H-GBH-FH
    PAD=0.09*inch; PW=0.72*inch; PH=BH-2*PAD; PX=PAD; PY=BY+PAD

    buf=io.BytesIO()
    c=Canvas(buf, pagesize=(W,H))

    # card
    rr(c,0,0,W,H,BR,fill_color=DARK_BG)
    rr(c,0,0,W,H,BR,stroke_color=GOLD,sw=1.8)
    c.setStrokeAlpha(0.22); rr(c,3.5,3.5,W-7,H-7,BR-2,stroke_color=GOLD,sw=0.4); c.setStrokeAlpha(1)

    # gold bar
    GBY=H-GBH
    rr(c,0,GBY,W,GBH,BR,fill_color=GOLD); drect(c,0,GBY,W,BR,fill=GOLD)
    c.setStrokeAlpha(0.6); c.setStrokeColor(GOLD_DARK); c.setLineWidth(1.0)
    c.line(0,GBY,W,GBY); c.setStrokeAlpha(1)

    # logo
    LR=0.185*inch; LCX=0.265*inch; LCY=H-GBH/2
    c.setFillColor(DARK_LOGO); c.circle(LCX,LCY,LR,fill=1,stroke=0)
    c.saveState()
    p=c.beginPath(); p.circle(LCX,LCY,LR); c.clipPath(p,stroke=0)
    c.drawImage(LOGO_PATH,LCX-LR,LCY-LR,width=LR*2.1,height=LR*2.1,mask='auto')
    c.restoreState()

    # company name
    BCX=W/2+0.04*inch; BCY=H-GBH/2
    txt(c,"PEAKS AND VALLEYS",BCX,BCY+0.038*inch,"Helvetica-Bold",7.8,DARK_LOGO,anchor="center")
    txt(c,"CONSTRUCTION",BCX,BCY-0.055*inch,"Helvetica",6,HexColor("#3a2500"),anchor="center")

    # footer
    rr(c,0,0,W,FH,BR,fill_color=FOOTER_BG); drect(c,0,FH-BR,W,BR,fill=FOOTER_BG)
    c.setStrokeColor(GOLD); c.setLineWidth(0.8); c.setStrokeAlpha(0.5)
    c.line(0,FH,W,FH); c.setStrokeAlpha(1)
    txt(c,"FORGED IN THE VALLEYS.  BUILT FOR THE PEAKS.",W/2,FH-0.195*inch,"Helvetica-Oblique",5.5,GOLD,anchor="center")
    txt(c,"ROOFING  \u00b7  SIDING  \u00b7  GUTTERS  \u00b7  STORM DAMAGE REPAIR",W/2,FH-0.33*inch,"Helvetica",4.2,DARK_SVC,anchor="center")

    # photo box
    rr(c,PX,PY,PW,PH,3,fill_color=HexColor("#1c1c1c"),stroke_color=GOLD,sw=1.0)
    if photo_bytes:
        try:
            ir=ImageReader(io.BytesIO(photo_bytes))
            c.saveState()
            p2=c.beginPath()
            p2.moveTo(PX+3,PY);       p2.lineTo(PX+PW-3,PY)
            p2.arcTo(PX+PW-6,PY,     PX+PW,PY+6,     -90,90)
            p2.lineTo(PX+PW,PY+PH-3)
            p2.arcTo(PX+PW-6,PY+PH-6,PX+PW,PY+PH,    0,  90)
            p2.lineTo(PX+3,PY+PH)
            p2.arcTo(PX,PY+PH-6,     PX+6,PY+PH,     90, 90)
            p2.lineTo(PX,PY+3)
            p2.arcTo(PX,PY,           PX+6,PY+6,      180,90)
            p2.close(); c.clipPath(p2,stroke=0)
            c.drawImage(ir,PX,PY,width=PW,height=PH,preserveAspectRatio=False,mask='auto')
            c.restoreState()
        except Exception:
            traceback.print_exc()
    else:
        ICX=PX+PW/2; ICY=PY+PH/2+0.02*inch
        c.setFillColor(HexColor("#2a2a2a")); c.circle(ICX,ICY+0.02*inch,0.055*inch,fill=1,stroke=0)
        c.setFillColor(HexColor("#3a3a3a")); c.circle(ICX,ICY+0.02*inch,0.03*inch,fill=1,stroke=0)
        txt(c,"PHOTO",ICX,PY+0.1*inch,"Helvetica",4.5,DIM_TXT,anchor="center")

    # content column
    CX=PX+PW+0.1*inch; CT=BY+BH-PAD-0.02*inch; NY=CT-0.11*inch
    txt(c,name.upper()[:22],CX,NY,"Helvetica-Bold",13,white)
    TY=NY-0.115*inch
    txt(c,title.upper()[:28],CX,TY,"Helvetica",5.5,GOLD)
    RY=TY-0.055*inch
    c.setStrokeColor(GOLD); c.setLineWidth(0.5); c.setStrokeAlpha(0.4)
    c.line(CX,RY,W-0.63*inch,RY); c.setStrokeAlpha(1)
    PHY=RY-0.08*inch;  txt(c,phone,CX,PHY,"Helvetica",5.8,LIGHT_TXT)
    EY=PHY-0.075*inch; txt(c,email[:42],CX,EY,"Helvetica",4.6,MID_TXT)

    # pill
    PLY=EY-0.11*inch; PLW=0.82*inch; PLH=0.1*inch
    c.saveState(); c.setFillColor(GOLD); c.setFillAlpha(0.12)
    rr(c,CX,PLY,PLW,PLH,PLH/2,fill_color=GOLD); c.restoreState()
    rr(c,CX,PLY,PLW,PLH,PLH/2,stroke_color=GOLD,sw=0.5)
    txt(c,"PEAKS EXTERIOR PRO",CX+PLW/2,PLY+0.028*inch,"Helvetica",4.0,GOLD,anchor="center")
    txt(c,"SERVING OREGON & WASHINGTON",CX,PLY-0.07*inch,"Helvetica",4.0,DIM_TXT)

    # QR
    QW=0.58*inch; QH=PH; QX=W-PAD-QW; QY=PY
    rr(c,QX,QY,QW,QH,3,fill_color=white)
    cs=0.094*inch
    qr_corner(c,QX+0.028*inch,QY+QH-0.028*inch-cs,cs)
    qr_corner(c,QX+QW-0.028*inch-cs,QY+QH-0.028*inch-cs,cs)
    qr_corner(c,QX+0.028*inch,QY+0.028*inch,cs)
    qr_dots(c,QX,QY,QW,QH)
    txt(c,"SCAN TO CONNECT",QX+QW/2,QY-0.045*inch,"Helvetica",3.5,DIM_TXT,anchor="center")

    c.setStrokeColor(GOLD); c.setLineWidth(0.5); c.setStrokeAlpha(0.3)
    c.line(PAD,FH+0.005*inch,W-PAD,FH+0.005*inch); c.setStrokeAlpha(1)

    c.save(); buf.seek(0)
    return buf.read()


# ── Email ──────────────────────────────────────────────────────────────────

def send_badge_email(to_email, name, pdf_bytes):
    smtp_host=os.environ["SMTP_HOST"]; smtp_port=int(os.environ.get("SMTP_PORT",587))
    smtp_user=os.environ["SMTP_USER"]; smtp_pass=os.environ["SMTP_PASS"]
    office=os.environ.get("OFFICE_EMAIL","office@peaksroofs.com")
    first=name.split()[0].title() if name else "Team"
    msg=MIMEMultipart()
    msg["From"]=f"Peaks and Valleys Construction <{smtp_user}>"
    msg["To"]=to_email; msg["CC"]=office
    msg["Subject"]=f"ID Badge Ready — {name.title()}"
    msg.attach(MIMEText(f"""Hi {first},

Your Peaks and Valleys Construction ID badge is attached and print-ready.

Print specs: 3.375" x 2.125" (CR80 standard badge)

Questions? Email us at {office}.

— Peaks and Valleys Construction
   FORGED IN THE VALLEYS. BUILT FOR THE PEAKS.
""","plain"))
    part=MIMEBase("application","pdf"); part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    safe=re.sub(r"[^a-zA-Z0-9_-]","_",name)
    part.add_header("Content-Disposition","attachment",filename=f"PVC_Badge_{safe}.pdf")
    msg.attach(part)
    with smtplib.SMTP(smtp_host,smtp_port) as s:
        s.ehlo(); s.starttls(); s.login(smtp_user,smtp_pass)
        s.sendmail(smtp_user,list({to_email,office}),msg.as_string())


# ── Routes ─────────────────────────────────────────────────────────────────

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status":"ok","service":"PVC Badge Generator"})

@app.route("/badge", methods=["POST"])
def badge_webhook():
    secret=os.environ.get("SECRET_KEY","")
    if secret and request.headers.get("X-PVC-Secret","")!=secret:
        return jsonify({"error":"Unauthorized"}),401
    try:
        if request.content_type and "multipart" in request.content_type:
            data=request.form; photo=request.files.get("headshot")
            photo_bytes=photo.read() if photo else None
        else:
            data=request.get_json(force=True) or {}; photo_bytes=None
            url=data.get("headshot_url") or data.get("headshot")
            if url and url.startswith("http"):
                r=requests.get(url,timeout=15)
                if r.status_code==200: photo_bytes=r.content
        name=(data.get("full_name") or data.get("name") or "").strip()
        title=(data.get("job_title") or data.get("title") or "").strip()
        phone=(data.get("phone") or "").strip()
        email=(data.get("email") or "").strip()
        if not name or not email:
            return jsonify({"error":"full_name and email are required"}),400
        pdf=generate_badge(name,title,phone,email,photo_bytes)
        send_badge_email(email,name,pdf)
        return jsonify({"success":True,"message":f"Badge emailed to {email}"}),200
    except Exception as e:
        traceback.print_exc(); return jsonify({"error":str(e)}),500

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)))
