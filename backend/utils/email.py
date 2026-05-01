"""
backend/utils/email.py
Sends OTP emails via SMTP.

Configuration (set as environment variables or in .env):
    SMTP_HOST      — default: smtp.gmail.com
    SMTP_PORT      — default: 587
    SMTP_USER      — your full email address  (e.g. yourapp@gmail.com)
    SMTP_PASSWORD  — app-password / SMTP password
    EMAIL_FROM     — display name + address  (default: same as SMTP_USER)

If SMTP_USER is not set the function falls back to console-print (dev mode).
If the send fails for any reason (bad address, auth error, network) it raises
RuntimeError so callers can surface "Email is invalid" to the user.
"""

from __future__ import annotations

import os
import random
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ── SMTP settings from environment ────────────────────────────────────────────
SMTP_HOST:     str = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT:     int = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER:     str = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD: str = os.environ.get("SMTP_PASSWORD", "")
EMAIL_FROM:    str = os.environ.get("EMAIL_FROM", SMTP_USER)

_DEV_MODE = not SMTP_USER   # True when no SMTP credentials configured


def _html_otp_email(otp: str, purpose: str = "Login") -> str:
    """Return a polished HTML email body for an OTP."""
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body  {{ font-family: 'Segoe UI', Arial, sans-serif; background:#0d1117; color:#e6edf3; margin:0; padding:0; }}
    .wrap {{ max-width:480px; margin:40px auto; background:#161b22; border-radius:12px;
             border:1px solid rgba(244,51,52,0.25); overflow:hidden; }}
    .hdr  {{ background:linear-gradient(135deg,#1a0a0a,#2d0c0c); padding:28px 32px; text-align:center; }}
    .hdr h1 {{ margin:0; font-size:1.3rem; color:#f43334; letter-spacing:2px; text-transform:uppercase; }}
    .body {{ padding:32px; text-align:center; }}
    .otp  {{ font-size:2.8rem; font-weight:800; letter-spacing:0.5em; color:#f43334;
             background:#0d1117; border-radius:8px; padding:18px 28px; display:inline-block;
             margin:20px 0; font-family:'Courier New',monospace; border:1px solid rgba(244,51,52,0.3); }}
    .note {{ font-size:0.82rem; color:#8b949e; margin-top:16px; line-height:1.6; }}
    .ftr  {{ padding:16px 32px; border-top:1px solid rgba(255,255,255,0.06);
             text-align:center; font-size:0.72rem; color:#8b949e; }}
  </style>
</head>
<body>
<div class="wrap">
  <div class="hdr">
    <h1>🔐 BEHAVE-SEC</h1>
  </div>
  <div class="body">
    <p style="font-size:1rem;margin-bottom:4px;">{purpose} Verification Code</p>
    <p style="color:#8b949e;font-size:0.85rem;margin-top:0;">
      Use the code below to complete your {purpose.lower()}. It expires in <strong>10 minutes</strong>.
    </p>
    <div class="otp">{otp}</div>
    <p class="note">
      If you did not request this code, please ignore this email.<br>
      Do not share this code with anyone.
    </p>
  </div>
  <div class="ftr">BEHAVE-SEC · Behavioral Biometric Security Platform</div>
</div>
</body>
</html>"""


def send_otp(recipient_email: str, otp: str, purpose: str = "Login") -> None:
    """
    Send an OTP to *recipient_email*.

    Dev mode (no SMTP_USER set): prints OTP to console, succeeds silently.
    Prod mode: sends via SMTP/TLS.  Raises RuntimeError on any failure so
    the caller can map it to "Email is invalid."
    """
    if _DEV_MODE:
        print(f"\n{'='*48}")
        print(f"🔒 [OTP DEV MODE] {purpose} OTP for {recipient_email}: {otp}")
        print(f"{'='*48}\n")
        return   # success in dev mode

    # Build message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"BEHAVE-SEC {purpose} Code: {otp}"
    msg["From"]    = f"BEHAVE-SEC Security <{EMAIL_FROM}>"
    msg["To"]      = recipient_email

    msg.attach(MIMEText(f"Your {purpose} OTP is: {otp}  (expires in 10 minutes)", "plain"))
    msg.attach(MIMEText(_html_otp_email(otp, purpose), "html"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=8) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(EMAIL_FROM or SMTP_USER, recipient_email, msg.as_string())
    except (smtplib.SMTPRecipientsRefused, smtplib.SMTPException,
            ConnectionRefusedError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"SMTP send failed: {exc}") from exc


def generate_otp() -> str:
    """Return a 6-digit numeric OTP string."""
    return str(random.randint(100_000, 999_999))
