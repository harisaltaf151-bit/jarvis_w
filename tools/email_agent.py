"""
JARVIS Tool — Email Agent
Read, compose, send, reply to, and manage emails via IMAP + SMTP.
Configure via ~/.jarvis/email.json or environment variables.
"""

import email
import imaplib
import json
import os
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


CFG_PATH = Path.home() / ".jarvis" / "email.json"


def _load_cfg() -> dict:
    """Load email config. Priority: env vars > config file > empty dict."""
    cfg = {}
    if CFG_PATH.exists():
        try:
            cfg = json.loads(CFG_PATH.read_text())
        except Exception:
            pass
    # env var overrides
    for key in ("EMAIL_ADDRESS", "EMAIL_PASSWORD", "SMTP_HOST", "SMTP_PORT",
                "IMAP_HOST", "IMAP_PORT"):
        val = os.getenv(key)
        if val:
            cfg[key.lower()] = val
    return cfg


def _gmail_defaults(cfg: dict) -> dict:
    addr = cfg.get("email_address", "")
    if "gmail" in addr and "smtp_host" not in cfg:
        cfg.setdefault("smtp_host",  "smtp.gmail.com")
        cfg.setdefault("smtp_port",  587)
        cfg.setdefault("imap_host",  "imap.gmail.com")
        cfg.setdefault("imap_port",  993)
    return cfg


class EmailAgent:

    def __init__(self):
        self._cfg = _gmail_defaults(_load_cfg())

    def setup_guide(self) -> str:
        """Return setup instructions."""
        guide = f"""
EMAIL SETUP — create {CFG_PATH}:

{{
  "email_address": "you@gmail.com",
  "email_password": "your-app-password",
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "imap_host": "imap.gmail.com",
  "imap_port": 993
}}

For Gmail: enable 2FA → generate App Password at myaccount.google.com/apppasswords
For Outlook: use smtp.office365.com:587 / outlook.office365.com:993
"""
        return guide.strip()

    def send(self, to: str, subject: str, body: str,
             cc: str = "", bcc: str = "", html: bool = False) -> dict:
        """Send an email."""
        cfg = self._cfg
        if not cfg.get("email_address"):
            return {"error": "Email not configured. Run setup_guide() for instructions."}

        msg = MIMEMultipart("alternative")
        msg["From"]    = cfg["email_address"]
        msg["To"]      = to
        msg["Subject"] = subject
        if cc:  msg["Cc"]  = cc
        if bcc: msg["Bcc"] = bcc

        part = MIMEText(body, "html" if html else "plain", "utf-8")
        msg.attach(part)

        recipients = [to] + ([cc] if cc else []) + ([bcc] if bcc else [])

        try:
            ctx = ssl.create_default_context()
            with smtplib.SMTP(cfg.get("smtp_host", "smtp.gmail.com"),
                              int(cfg.get("smtp_port", 587))) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.login(cfg["email_address"], cfg["email_password"])
                server.sendmail(cfg["email_address"], recipients, msg.as_string())
            return {"ok": True, "to": to, "subject": subject}
        except Exception as exc:
            return {"error": str(exc)}

    def fetch_inbox(self, count: int = 10, folder: str = "INBOX",
                    unread_only: bool = False) -> list[dict]:
        """Fetch recent emails from inbox."""
        cfg = self._cfg
        if not cfg.get("email_address"):
            return [{"error": "Email not configured."}]
        try:
            mail = imaplib.IMAP4_SSL(cfg.get("imap_host", "imap.gmail.com"),
                                     int(cfg.get("imap_port", 993)))
            mail.login(cfg["email_address"], cfg["email_password"])
            mail.select(folder)

            criterion = "(UNSEEN)" if unread_only else "ALL"
            _, data   = mail.search(None, criterion)
            ids       = data[0].split()
            ids       = ids[-count:][::-1]   # newest first

            messages = []
            for uid in ids:
                _, raw = mail.fetch(uid, "(RFC822)")
                msg    = email.message_from_bytes(raw[0][1])
                body   = _extract_body(msg)
                messages.append({
                    "id":      uid.decode(),
                    "from":    msg.get("From", ""),
                    "to":      msg.get("To", ""),
                    "subject": msg.get("Subject", "(no subject)"),
                    "date":    msg.get("Date", ""),
                    "body":    body[:500],
                    "unread":  "\\Seen" not in (msg.get("Flags") or ""),
                })
            mail.logout()
            return messages
        except Exception as exc:
            return [{"error": str(exc)}]

    def reply(self, original_subject: str, to: str,
              body: str) -> dict:
        """Reply to an email thread."""
        subject = original_subject if original_subject.startswith("Re:") else f"Re: {original_subject}"
        return self.send(to=to, subject=subject, body=body)

    def search_emails(self, query: str, folder: str = "INBOX") -> list[dict]:
        """Search emails by subject or sender."""
        cfg = self._cfg
        if not cfg.get("email_address"):
            return [{"error": "Email not configured."}]
        try:
            mail = imaplib.IMAP4_SSL(cfg.get("imap_host", "imap.gmail.com"),
                                     int(cfg.get("imap_port", 993)))
            mail.login(cfg["email_address"], cfg["email_password"])
            mail.select(folder)

            # search subject OR from
            _, d1 = mail.search(None, f'(SUBJECT "{query}")')
            _, d2 = mail.search(None, f'(FROM "{query}")')
            ids   = list(set(d1[0].split() + d2[0].split()))[-20:]

            results = []
            for uid in ids:
                _, raw = mail.fetch(uid, "(RFC822)")
                msg    = email.message_from_bytes(raw[0][1])
                results.append({
                    "id":      uid.decode(),
                    "from":    msg.get("From", ""),
                    "subject": msg.get("Subject", ""),
                    "date":    msg.get("Date", ""),
                })
            mail.logout()
            return results
        except Exception as exc:
            return [{"error": str(exc)}]

    def draft(self, to: str, subject: str,
              context: str = "") -> dict:
        """Return a drafted email (does NOT send — for review)."""
        return {
            "status":  "draft",
            "to":      to,
            "subject": subject,
            "body":    f"[AI-drafted email based on: {context}]\n\nDear {to.split('@')[0].title()},\n\n{context}\n\nBest regards",
            "note":    "Call send() with this data to deliver.",
        }


# ── helpers ────────────────────────────────────────────────────────────────────
def _extract_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                try:
                    return part.get_payload(decode=True).decode("utf-8", errors="replace")
                except Exception:
                    pass
    else:
        try:
            return msg.get_payload(decode=True).decode("utf-8", errors="replace")
        except Exception:
            return ""
    return ""
