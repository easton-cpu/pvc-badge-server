"""
Peaks and Valleys Construction — Contract Generation Server
Endpoint: POST /generate-contract
Flow: ReportLab PDF → SignWell → Google Drive (OAuth) → Email both parties
"""

import os, io, json, base64, requests
from datetime import datetime
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

app = Flask(__name__)
CORS(app)

# ─── ENV VARS (set all of these on Render) ──────────────────────────────────
os.environ.setdefault('SIGNWELL_API_KEY', '')
os.environ.setdefault('GOOGLE_DRIVE_FOLDER_ID', '1KKm4n52UpS1TdpEymYyLof2zrH1Rp2rx')
os.environ.setdefault('GOOGLE_CLIENT_ID', '')        # from Google Cloud OAuth credentials
os.environ.setdefault('GOOGLE_CLIENT_SECRET', '')    # from Google Cloud OAuth credentials
os.environ.setdefault('GOOGLE_REFRESH_TOKEN', '')    # obtained once via /auth flow below
os.environ.setdefault('SMTP_HOST', 'smtp.gmail.com')
os.environ.setdefault('SMTP_PORT', '587')
os.environ.setdefault('SMTP_USER', 'office@peaksroofs.com')
os.environ.setdefault('SMTP_PASS', '')
os.environ.setdefault('OFFICE_EMAIL', 'office@peaksroofs.com')

SIGNWELL_API_KEY = os.environ['SIGNWELL_API_KEY']
DRIVE_FOLDER_ID  = os.environ['GOOGLE_DRIVE_FOLDER_ID']
CLIENT_ID        = os.environ['GOOGLE_CLIENT_ID']
CLIENT_SECRET    = os.environ['GOOGLE_CLIENT_SECRET']
REFRESH_TOKEN    = os.environ['GOOGLE_REFRESH_TOKEN']
SMTP_HOST        = os.environ['SMTP_HOST']
SMTP_PORT        = int(os.environ['SMTP_PORT'])
SMTP_USER        = os.environ['SMTP_USER']
SMTP_PASS        = os.environ['SMTP_PASS']
OFFICE_EMAIL     = os.environ['OFFICE_EMAIL']

SCOPES = ['https://www.googleapis.com/auth/drive.file']

# ─── COLORS ────────────────────────────────────────────────────────────────
GOLD  = colors.HexColor('#C8912A')
BLACK = colors.HexColor('#0a0a0a')
WHITE = colors.white
GRAY  = colors.HexColor('#f5f3ef')
MGRAY = colors.HexColor('#888680')
DGRAY = colors.HexColor('#2a2a2a')

# ─── PDF GENERATION ────────────────────────────────────────────────────────
def fmt_money(v):
    try:
        return f"${float(v):,.2f}"
    except:
        return "$0.00"

def build_contract_pdf(data: dict) -> bytes:
    customer      = data['customer']
    project       = data['project']
    change_orders = data.get('changeOrders', [])
    notes         = data.get('specialNotes', '')
    rep           = data.get('rep', '')
    date_str      = data.get('contractDate', datetime.now().strftime('%Y-%m-%d'))
    try:
        contract_date = datetime.strptime(date_str, '%Y-%m-%d').strftime('%B %d, %Y')
    except:
        contract_date = date_str

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.65*inch, rightMargin=0.65*inch,
        topMargin=0.65*inch,  bottomMargin=0.75*inch,
    )

    def S(name, **kw):
        return ParagraphStyle(name, **kw)

    sSection = S('sSection', fontName='Helvetica-Bold',   fontSize=8,   textColor=GOLD,  spaceAfter=4,  leading=10, letterSpacing=1.2)
    sBody    = S('sBody',    fontName='Helvetica',        fontSize=9,   textColor=DGRAY, spaceAfter=3,  leading=13)
    sSmall   = S('sSmall',   fontName='Helvetica',        fontSize=7.5, textColor=MGRAY, spaceAfter=2,  leading=10)
    sBold    = S('sBold',    fontName='Helvetica-Bold',   fontSize=9,   textColor=DGRAY, leading=13)
    sLegal   = S('sLegal',   fontName='Helvetica',        fontSize=7,   textColor=MGRAY, leading=10,    spaceAfter=4)
    sNote    = S('sNote',    fontName='Helvetica-Oblique',fontSize=8.5, textColor=DGRAY, leading=12,    spaceAfter=3)

    story = []
    W = doc.width

    # HEADER
    header_data = [[
        Paragraph('<b>PEAKS AND VALLEYS</b><br/><font size=7 color="#C8912A">CONSTRUCTION LLC</font>',
                  S('hb', fontName='Helvetica-Bold', fontSize=13, textColor=BLACK, leading=16)),
        Paragraph('CUSTOMER PURCHASE AGREEMENT',
                  S('hd', fontName='Helvetica-Bold', fontSize=11, textColor=BLACK, alignment=TA_CENTER, letterSpacing=1)),
        Paragraph(f'Date: <b>{contract_date}</b>',
                  S('hdt', fontName='Helvetica', fontSize=8.5, textColor=DGRAY, alignment=TA_RIGHT, leading=12))
    ]]
    ht = Table(header_data, colWidths=[W*0.32, W*0.36, W*0.32])
    ht.setStyle(TableStyle([
        ('VALIGN',       (0,0),(-1,-1), 'MIDDLE'),
        ('LINEBELOW',    (0,0),(-1,-1), 1.5, GOLD),
        ('BOTTOMPADDING',(0,0),(-1,-1), 8),
        ('TOPPADDING',   (0,0),(-1,-1), 4),
    ]))
    story.append(ht)
    story.append(Spacer(1, 10))

    # CUSTOMER INFO
    story.append(Paragraph('CUSTOMER INFORMATION', sSection))
    full_addr = f"{customer.get('address','')}   {customer.get('city','')}  {customer.get('state','')}  {customer.get('zip','')}"
    ci_data = [
        [Paragraph(f"<b>Name:</b>  {customer.get('name','')}", sBody),   Paragraph(f"<b>Phone:</b>  {customer.get('phone1','')}", sBody)],
        [Paragraph(f"<b>Address:</b>  {full_addr}", sBody),              Paragraph(f"<b>Alt Phone:</b>  {customer.get('phone2','')}", sBody)],
        [Paragraph(f"<b>Email:</b>  {customer.get('email','')}", sBody), Paragraph(f"<b>Sales Rep:</b>  {rep}", sBody)],
    ]
    ci = Table(ci_data, colWidths=[W*0.58, W*0.42])
    ci.setStyle(TableStyle([
        ('BOX',          (0,0),(-1,-1), 0.5, colors.HexColor('#d0ccc8')),
        ('INNERGRID',    (0,0),(-1,-1), 0.5, colors.HexColor('#e8e4e0')),
        ('BACKGROUND',   (0,0),(-1,-1), GRAY),
        ('TOPPADDING',   (0,0),(-1,-1), 5),
        ('BOTTOMPADDING',(0,0),(-1,-1), 5),
        ('LEFTPADDING',  (0,0),(-1,-1), 8),
    ]))
    story.append(ci)
    story.append(Spacer(1, 12))

    # SCOPE OF WORK
    story.append(Paragraph('SCOPE OF WORK', sSection))
    st = Table([[Paragraph(project.get('scopeOfWork', ''), sBody)]], colWidths=[W])
    st.setStyle(TableStyle([
        ('BOX',          (0,0),(-1,-1), 0.5, colors.HexColor('#d0ccc8')),
        ('BACKGROUND',   (0,0),(-1,-1), GRAY),
        ('TOPPADDING',   (0,0),(-1,-1), 8),
        ('BOTTOMPADDING',(0,0),(-1,-1), 8),
        ('LEFTPADDING',  (0,0),(-1,-1), 8),
        ('RIGHTPADDING', (0,0),(-1,-1), 8),
    ]))
    story.append(st)
    story.append(Spacer(1, 12))

    # CHANGE ORDERS
    if change_orders:
        story.append(Paragraph('CHANGE ORDERS / ADDITIONAL WORK', sSection))
        co_data = [[
            Paragraph('<b>Item</b>', sBold),
            Paragraph('<b>Description</b>', sBold),
            Paragraph('<b>Price</b>', S('sbr', fontName='Helvetica-Bold', fontSize=9, textColor=DGRAY, alignment=TA_RIGHT, leading=13))
        ]]
        for i, co in enumerate(change_orders, 1):
            co_data.append([
                Paragraph(f"{i}. {co.get('title','')}", sBody),
                Paragraph(co.get('description',''), sBody),
                Paragraph(fmt_money(co.get('price',0)), S('smr', fontName='Helvetica', fontSize=9, textColor=DGRAY, alignment=TA_RIGHT, leading=13))
            ])
        cot = Table(co_data, colWidths=[W*0.22, W*0.54, W*0.24])
        cot.setStyle(TableStyle([
            ('BOX',          (0,0),(-1,-1), 0.5, colors.HexColor('#d0ccc8')),
            ('INNERGRID',    (0,0),(-1,-1), 0.5, colors.HexColor('#e8e4e0')),
            ('BACKGROUND',   (0,0),(2,0),   colors.HexColor('#e8e4e0')),
            ('BACKGROUND',   (0,1),(-1,-1), GRAY),
            ('TOPPADDING',   (0,0),(-1,-1), 5),
            ('BOTTOMPADDING',(0,0),(-1,-1), 5),
            ('LEFTPADDING',  (0,0),(-1,-1), 8),
        ]))
        story.append(cot)
        story.append(Spacer(1, 12))

    # FINANCIAL SUMMARY
    story.append(Paragraph('FINANCIAL SUMMARY', sSection))
    co_total = sum(float(c.get('price',0)) for c in change_orders)
    fin_data = [
        [Paragraph('<b>Base Price</b> (All Discounts Included)', sBold),
         Paragraph(fmt_money(project.get('basePrice',0)), S('mr', fontName='Helvetica', fontSize=9, textColor=DGRAY, alignment=TA_RIGHT))],
    ]
    if change_orders:
        fin_data.append([Paragraph('Change Orders Total', sBody),
                         Paragraph(fmt_money(co_total), S('mr2', fontName='Helvetica', fontSize=9, textColor=DGRAY, alignment=TA_RIGHT))])
    if float(project.get('tax', 0)) > 0:
        fin_data.append([Paragraph('Tax', sBody),
                         Paragraph(fmt_money(project.get('tax',0)), S('mr3', fontName='Helvetica', fontSize=9, textColor=DGRAY, alignment=TA_RIGHT))])
    fin_data.append([
        Paragraph('<b>GRAND TOTAL</b>', S('gt', fontName='Helvetica-Bold', fontSize=10, textColor=WHITE)),
        Paragraph(f"<b>{fmt_money(project.get('grandTotal',0))}</b>",
                  S('gtr', fontName='Helvetica-Bold', fontSize=10, textColor=WHITE, alignment=TA_RIGHT))
    ])
    fnt = Table(fin_data, colWidths=[W*0.72, W*0.28])
    fnt.setStyle(TableStyle([
        ('BOX',          (0,0),(-1,-1), 0.5, colors.HexColor('#d0ccc8')),
        ('INNERGRID',    (0,0),(-1,-1), 0.5, colors.HexColor('#e8e4e0')),
        ('BACKGROUND',   (0,0),(-1,-2), GRAY),
        ('BACKGROUND',   (0,-1),(-1,-1), GOLD),
        ('TOPPADDING',   (0,0),(-1,-1), 5),
        ('BOTTOMPADDING',(0,0),(-1,-1), 5),
        ('LEFTPADDING',  (0,0),(-1,-1), 8),
        ('RIGHTPADDING', (0,0),(-1,-1), 8),
    ]))
    story.append(fnt)
    story.append(Spacer(1, 12))

    # PAYMENT SCHEDULE
    story.append(Paragraph('PAYMENT SCHEDULE', sSection))
    pmt   = project.get('payment', {})
    grand = float(project.get('grandTotal', 0))
    def pct(amt):
        try:
            return f"({round(float(amt)/grand*100,1)}%)" if grand > 0 else ""
        except:
            return ""
    ps_data = [
        [Paragraph('<b>Payment</b>', sBold), Paragraph('<b>Note</b>', sBold),
         Paragraph('<b>Amount</b>', S('psbh', fontName='Helvetica-Bold', fontSize=9, textColor=DGRAY, alignment=TA_RIGHT))],
        [Paragraph(f"Initial Deposit {pct(pmt.get('deposit1',{}).get('amount',0))}", sBody),
         Paragraph(pmt.get('deposit1',{}).get('note',''), sBody),
         Paragraph(fmt_money(pmt.get('deposit1',{}).get('amount',0)), S('psr', fontName='Helvetica', fontSize=9, textColor=DGRAY, alignment=TA_RIGHT))],
        [Paragraph(f"2nd Payment — Job Start {pct(pmt.get('deposit2',{}).get('amount',0))}", sBody),
         Paragraph(pmt.get('deposit2',{}).get('note',''), sBody),
         Paragraph(fmt_money(pmt.get('deposit2',{}).get('amount',0)), S('psr2', fontName='Helvetica', fontSize=9, textColor=DGRAY, alignment=TA_RIGHT))],
        [Paragraph(f"Final Payment *Max 10% Retainage {pct(pmt.get('final',{}).get('amount',0))}", sBody),
         Paragraph(pmt.get('final',{}).get('note',''), sBody),
         Paragraph(fmt_money(pmt.get('final',{}).get('amount',0)), S('psr3', fontName='Helvetica', fontSize=9, textColor=DGRAY, alignment=TA_RIGHT))],
    ]
    pst = Table(ps_data, colWidths=[W*0.32, W*0.44, W*0.24])
    pst.setStyle(TableStyle([
        ('BOX',          (0,0),(-1,-1), 0.5, colors.HexColor('#d0ccc8')),
        ('INNERGRID',    (0,0),(-1,-1), 0.5, colors.HexColor('#e8e4e0')),
        ('BACKGROUND',   (0,0),(-1, 0), colors.HexColor('#e8e4e0')),
        ('BACKGROUND',   (0,1),(-1,-1), GRAY),
        ('TOPPADDING',   (0,0),(-1,-1), 5),
        ('BOTTOMPADDING',(0,0),(-1,-1), 5),
        ('LEFTPADDING',  (0,0),(-1,-1), 8),
        ('RIGHTPADDING', (0,0),(-1,-1), 8),
    ]))
    story.append(pst)
    story.append(Spacer(1, 12))

    # SPECIAL NOTES
    if notes:
        story.append(Paragraph('HOMEOWNER NOTES &amp; SPECIAL REQUESTS', sSection))
        nt = Table([[Paragraph(f"<i>{notes}</i>", sNote)]], colWidths=[W])
        nt.setStyle(TableStyle([
            ('BOX',          (0,0),(-1,-1), 1, GOLD),
            ('BACKGROUND',   (0,0),(-1,-1), colors.HexColor('#fdf8f0')),
            ('TOPPADDING',   (0,0),(-1,-1), 8),
            ('BOTTOMPADDING',(0,0),(-1,-1), 8),
            ('LEFTPADDING',  (0,0),(-1,-1), 10),
            ('RIGHTPADDING', (0,0),(-1,-1), 10),
        ]))
        story.append(nt)
        story.append(Spacer(1, 12))

    # TERMS & CONDITIONS
    story.append(Paragraph('TERMS AND CONDITIONS', sSection))
    terms = [
        "<b>Contractor:</b> Peaks and Valleys Construction LLC dba Peaks and Valleys Construction (\"Contractor\"), License No. CCPEAKSVC741KN, is independently owned and operated and will perform all Work in a workmanlike manner in accordance with applicable building codes and law. Contractor will not commence or will immediately discontinue Work upon discovery of concealed, unforeseen, or hazardous conditions.",
        "<b>Customer Responsibilities:</b> Customer agrees to: provide written notice of any easements or legal encumbrances; facilitate utility marking; ensure work areas are free of hazards; allow professional access during normal working hours; provide power and sanitary access at no cost to Contractor; keep unattended minors and pets away from work areas; and not assign this contract without Contractor's written consent.",
        "<b>Pre-existing Conditions:</b> Contractor is not responsible for pre-existing conditions including unforeseen rotted or damaged wood, concealed leaks, mold, or additional material layers discovered after Work commences. Any additional work to address such conditions requires a written Change Order signed by both parties.",
        "<b>Limited Warranty:</b> Contractor warrants workmanship for ten (10) years from completion. During the warranty period, Contractor will repair at no charge any defects due to faulty workmanship. Warranty does not cover acts of God, repairs by others, color variation, abuse, neglect, normal wear and tear, or improper maintenance. Materials are covered exclusively by the Manufacturer's warranty. Contractor's liability shall not exceed the total paid under this contract.",
        "<b>Cancellation:</b> Customer may cancel without penalty by written notice by midnight on the third business day after execution. Verbal notices are not effective. After the three-day period, termination by Customer incurs: (i) 10% of contract price before material ordering; (ii) 25% after material ordering; (iii) actual costs incurred; or (iv) pro-rated price for work performed — whichever is greater.",
        "<b>Non-Payment:</b> Final payment is due upon completion. Invoices unpaid after thirty (30) days void all warranties. A finance charge of <b>10%</b> of the outstanding balance will be applied to any unpaid balance more than thirty (30) days past due. A $50.00 processing fee applies to all returned checks.",
        "<b>Washington State Notice:</b> Contractor is registered in Washington. Bond: $12,000. General liability: $1,000,000. Workers' compensation maintained. YOUR PROPERTY MAY BE LIENED if suppliers, employees, or subcontractors are not paid. Customer may withhold a contractually defined retainage percentage.",
        "<b>Non-Disparagement &amp; Legal Action:</b> Both parties agree to refrain from disparaging conduct. In the event legal action is required to enforce payment or contract rights, Customer shall be liable for all attorneys' fees, expenses, and costs incurred by Contractor.",
        "<b>General:</b> Verbal agreements are not binding. All agreements must be in writing. No modification of this contract is effective unless in writing and signed by both parties. Customer releases Contractor from liability for health issues arising from pre-existing mold, asbestos, or lead-based paints.",
    ]
    for text in terms:
        story.append(Paragraph(text, sLegal))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 14))

    # SIGNATURE BLOCK
    story.append(HRFlowable(width=W, thickness=0.5, color=GOLD))
    story.append(Spacer(1, 8))
    story.append(Paragraph('SIGNATURES', sSection))
    sig_data = [
        [Paragraph('<b>Peaks and Valleys Construction Representative</b>', sBody), Paragraph('<b>HomeOwner / Buyer</b>', sBody)],
        [Paragraph(f'<b>{rep}</b>', S('srep', fontName='Helvetica-Bold', fontSize=10, textColor=DGRAY)), Paragraph('_________________________________', sBody)],
        [Paragraph('Signature: _______________________________', sSmall), Paragraph('Signature: _______________________________', sSmall)],
        [Paragraph(f'Date: {contract_date}', sSmall), Paragraph('Date: _________________', sSmall)],
    ]
    sigt = Table(sig_data, colWidths=[W*0.5, W*0.5])
    sigt.setStyle(TableStyle([
        ('VALIGN',       (0,0),(-1,-1), 'TOP'),
        ('TOPPADDING',   (0,0),(-1,-1), 6),
        ('BOTTOMPADDING',(0,0),(-1,-1), 4),
        ('LEFTPADDING',  (0,0),(-1,-1), 0),
        ('LINEABOVE',    (0,2),(1,2), 0.5, colors.HexColor('#d0ccc8')),
    ]))
    story.append(sigt)
    story.append(Spacer(1, 12))

    # FOOTER
    story.append(HRFlowable(width=W, thickness=0.3, color=colors.HexColor('#d0ccc8')))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'Peaks and Valleys Construction LLC dba Peaks and Valleys Construction  ·  office@peaksroofs.com  ·  peaksroofs.com  ·  License CCPEAKSVC741KN',
        S('footer', fontName='Helvetica', fontSize=7, textColor=MGRAY, alignment=TA_CENTER, leading=10)
    ))
    story.append(Paragraph(
        '*By signing above, Customer acknowledges having read and accepted these Terms and Conditions in their entirety.',
        S('footer2', fontName='Helvetica-Oblique', fontSize=7, textColor=MGRAY, alignment=TA_CENTER, leading=10)
    ))

    doc.build(story)
    return buf.getvalue()

# ─── GOOGLE DRIVE (OAuth refresh token) ────────────────────────────────────
def get_drive_service():
    creds = Credentials(
        token=None,
        refresh_token=REFRESH_TOKEN,
        token_uri='https://oauth2.googleapis.com/token',
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scopes=SCOPES,
    )
    creds.refresh(GoogleRequest())
    return build('drive', 'v3', credentials=creds)

def upload_to_drive(pdf_bytes: bytes, filename: str) -> str:
    service   = get_drive_service()
    file_meta = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
    media     = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype='application/pdf', resumable=False)
    uploaded  = service.files().create(body=file_meta, media_body=media, fields='id,webViewLink').execute()
    return uploaded.get('webViewLink', '')

# ─── ONE-TIME AUTH ROUTES (run once to get refresh token) ──────────────────
@app.route('/auth')
def auth():
    """Visit this URL once in your browser to start the OAuth flow."""
    if not CLIENT_ID:
        return "GOOGLE_CLIENT_ID not set in environment variables.", 400
    redirect_uri = request.url_root.rstrip('/') + '/auth/callback'
    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=https://www.googleapis.com/auth/drive.file"
        f"&access_type=offline"
        f"&prompt=consent"
    )
    return redirect(url)

@app.route('/auth/callback')
def auth_callback():
    """Google redirects here after you approve. Displays the refresh token."""
    code         = request.args.get('code')
    redirect_uri = request.url_root.rstrip('/') + '/auth/callback'
    resp = requests.post('https://oauth2.googleapis.com/token', data={
        'code':          code,
        'client_id':     CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'redirect_uri':  redirect_uri,
        'grant_type':    'authorization_code',
    })
    tokens = resp.json()
    refresh_token = tokens.get('refresh_token', '')
    if not refresh_token:
        return f"<pre>Error — no refresh token returned.\n\nFull response:\n{json.dumps(tokens, indent=2)}</pre>", 400
    return f"""
    <h2>Success!</h2>
    <p>Copy this refresh token and add it to Render as <b>GOOGLE_REFRESH_TOKEN</b>:</p>
    <textarea rows="4" cols="80" onclick="this.select()">{refresh_token}</textarea>
    <p>Once saved on Render, Drive uploads will work automatically.</p>
    """

# ─── SIGNWELL ──────────────────────────────────────────────────────────────
def send_to_signwell(pdf_bytes: bytes, customer: dict, rep: str, contract_date: str) -> dict:
    b64           = base64.b64encode(pdf_bytes).decode()
    customer_name = customer.get('name', 'Customer')
    safe_name     = customer_name.replace(' ', '_')
    filename      = f"PVC_Contract_{safe_name}_{contract_date}.pdf"

  payload = {
        "files": [{"name": filename, "file_base64": b64}],
        "recipients": [{"id": "signer_1", "name": customer_name, "email": customer.get("email")}],
        "fields": [[
            {"recipient_id": "signer_1", "type": "signature", "required": True, "page": 1, "x": 20, "y": 88, "width": 26, "height": 5},
            {"recipient_id": "signer_1", "type": "date", "required": True, "page": 1, "x": 55, "y": 88, "width": 16, "height": 5},
        ]],
        "message": f"Hi {customer_name},\n\nPlease review and sign your Peaks and Valleys Construction contract. If you have questions, contact {rep} or email office@peaksroofs.com.\n\nThank you for choosing Peaks and Valleys Construction!",
        "subject": "Your Peaks & Valleys Contract — Please Sign",
        "send_emails": True,
    }

    resp = requests.post(
        'https://www.signwell.com/api/v1/documents/',
        json=payload,
        headers={'X-Api-Key': SIGNWELL_API_KEY, 'Content-Type': 'application/json'},
        timeout=30
    )
    if not resp.ok:
        raise Exception(f"SignWell error {resp.status_code}: {resp.text} | Payload keys sent: {list(payload.keys())}")
    return resp.json()

# ─── EMAIL ─────────────────────────────────────────────────────────────────
def send_email_with_attachment(to_email, subject, body, pdf_bytes, filename):
    msg            = MIMEMultipart()
    msg['From']    = SMTP_USER
    msg['To']      = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(pdf_bytes)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
    msg.attach(part)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, to_email, msg.as_string())

def download_signed_pdf_from_signwell(doc_id):
    try:
        resp = requests.get(
            f'https://www.signwell.com/api/v1/documents/{doc_id}/completed_pdf/',
            headers={'X-Api-Key': SIGNWELL_API_KEY},
            timeout=20
        )
        if resp.ok:
            return resp.content
    except:
        pass
    return None

# ─── ROUTES ────────────────────────────────────────────────────────────────
@app.route('/', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'service': 'PVC Contract Server'})

@app.route('/generate-contract', methods=['POST'])
def generate_contract():
    try:
        data          = request.get_json(force=True)
        customer      = data.get('customer', {})
        contract_date = data.get('contractDate', datetime.now().strftime('%Y-%m-%d'))
        rep           = data.get('rep', 'Your Representative')

        pdf_bytes  = build_contract_pdf(data)
        name_slug  = customer.get('name','Customer').replace(' ','_')
        date_slug  = contract_date.replace('-','')
        filename   = f"PVC_Contract_{name_slug}_{date_slug}.pdf"

        sw_result = send_to_signwell(pdf_bytes, customer, rep, contract_date)
        doc_id    = sw_result.get('id', 'unknown')

        app.config.setdefault('PENDING_CONTRACTS', {})[doc_id] = {
            'customer':  customer,
            'rep':       rep,
            'filename':  filename,
            'pdf_bytes': pdf_bytes,
        }

        return jsonify({'success': True, 'signwell_document_id': doc_id,
                        'message': f'Contract sent to {customer.get("email")} for signing.'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/signwell-webhook', methods=['POST'])
def signwell_webhook():
    try:
        payload = request.get_json(force=True)
        event   = payload.get('event_type', '')

        if event not in ('document_completed', 'document_signed'):
            return jsonify({'received': True})

        doc_id        = payload.get('data', {}).get('id') or payload.get('document', {}).get('id')
        pending       = app.config.get('PENDING_CONTRACTS', {})
        contract_info = pending.get(doc_id)

        if not contract_info:
            signed_pdf = download_signed_pdf_from_signwell(doc_id)
            if not signed_pdf:
                return jsonify({'error': 'Contract not found'}), 404
            customer  = {}
            rep       = ''
            filename  = f"PVC_SignedContract_{doc_id}.pdf"
            pdf_bytes = signed_pdf
        else:
            customer  = contract_info['customer']
            rep       = contract_info['rep']
            filename  = contract_info['filename'].replace('Contract_', 'SignedContract_')
            pdf_bytes = download_signed_pdf_from_signwell(doc_id) or contract_info['pdf_bytes']

        # Drive upload — enabled once GOOGLE_REFRESH_TOKEN is set on Render
        drive_link = ''
        if os.environ.get('GOOGLE_REFRESH_TOKEN'):
            try:
                drive_link = upload_to_drive(pdf_bytes, filename)
            except Exception as drive_err:
                print(f"Drive upload skipped: {drive_err}")

        if customer.get('email'):
            send_email_with_attachment(
                to_email=customer['email'],
                subject='Your Signed Peaks & Valleys Construction Contract',
                body=f"Hi {customer.get('name','')},\n\nThank you for signing! Attached is your fully executed contract.\n\nQuestions? Contact us at office@peaksroofs.com.\n\nPeaks and Valleys Construction",
                pdf_bytes=pdf_bytes,
                filename=filename
            )

        office_body = f"Signed contract received from {customer.get('name','')} ({customer.get('email','')}).\n\nRep: {rep}"
        if drive_link:
            office_body += f"\n\nDrive: {drive_link}"
        send_email_with_attachment(
            to_email=OFFICE_EMAIL,
            subject=f'Signed Contract — {customer.get("name","Unknown")}',
            body=office_body,
            pdf_bytes=pdf_bytes,
            filename=filename
        )

        pending.pop(doc_id, None)
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=10000)
