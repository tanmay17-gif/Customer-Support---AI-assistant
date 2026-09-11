"""
Gmail Service — IMAP + email fetching + draft creation.
Uses a SECONDARY / TEST Gmail account with an App Password. Never auto-sends.
"""
import imaplib
import email
import base64
import re
from email.utils import parsedate_to_datetime
from email.message import EmailMessage
from typing import Optional
from loguru import logger

from app.core.config import settings

def _get_imap_connection() -> Optional[imaplib.IMAP4_SSL]:
    if not settings.GMAIL_ADDRESS or not settings.GMAIL_APP_PASSWORD:
        return None
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        return mail
    except Exception as e:
        logger.error(f"IMAP Connection failed: {e}")
        return None

def is_authenticated() -> bool:
    """Check if IMAP credentials are valid."""
    mail = _get_imap_connection()
    if mail:
        try:
            mail.logout()
        except Exception:
            pass
        return True
    return False

def get_authenticated_email() -> Optional[str]:
    if is_authenticated():
        return settings.GMAIL_ADDRESS
    return None

def fetch_unread_emails(max_results: int = 20) -> list[dict]:
    """Fetch unread Gmail messages and return as IncomingEmail-compatible dicts."""
    mail = _get_imap_connection()
    if not mail:
        return []
    
    try:
        mail.select("INBOX")
        status, response = mail.search(None, "UNSEEN")
        if status != "OK":
            return []
            
        msg_nums = response[0].split()
        # limit to max_results
        msg_nums = msg_nums[-max_results:] if max_results else msg_nums
        
        emails = []
        for num in msg_nums:
            status, msg_data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                continue
                
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    email_dict = _parse_imap_message(msg, num.decode('utf-8'))
                    if email_dict:
                        emails.append(email_dict)
        return emails
    finally:
        try:
            mail.logout()
        except Exception:
            pass

def _parse_imap_message(msg: email.message.Message, imap_uid: str) -> Optional[dict]:
    """Parse a raw IMAP message into IncomingEmail-compatible dict."""
    try:
        from_header = msg.get("From", "Unknown <unknown@example.com>")
        subject = msg.get("Subject", "(No Subject)")
        date_str = msg.get("Date", "")
        message_id = msg.get("Message-ID", f"imap-{imap_uid}").strip('<>')

        # Extract sender name + email
        import email.utils
        from_name, from_email = email.utils.parseaddr(from_header)
        if not from_name:
            from_name = from_email

        # ── LOG ALL INCOMING EMAILS FOR DEBUGGING ──
        logger.info(f"FETCHED IMAP EMAIL - Sender: {from_email} | Subject: {subject}")

        # ── FILTERING OUT AUTOMATED EMAILS ──
        lower_email = from_email.lower()
        lower_subject = subject.lower()
        
        # Block automated/system sender domains and patterns
        blocked_senders = [
            "no-reply", "noreply", "mailer-daemon", "postmaster",
            "accounts.google.com", "security-noreply", "alerts@",
            "notifications@", "notify@", "do-not-reply", "donotreply",
            "info@google", "google.com", "googlemail.com",
            "mail.instagram", "facebook.com", "linkedin.com",
            "twitter.com", "amazon.com", "paypal.com",
            "bounce", "auto-confirm", "support@github",
        ]
        if any(b in lower_email for b in blocked_senders):
            logger.info(f"FILTERED OUT: Matches blocked sender ({from_email})")
            return None
            
        # Block system/automated subject lines
        blocked_subjects = [
            "security alert", "2-step verification", "you shared some google account data",
            "sign-in", "critical security", "password reset", "verification code",
            "new device", "sign in attempt", "suspicious", "unsubscribe",
            "newsletter", "promotion", "offer", "sale", "discount", "deal",
            "confirm your", "click here", "click to", "activate your",
            "invoice from", "your receipt", "order confirmation",
            "delivery notification", "tracking", "shipped",
            "automatic reply", "out of office", "auto-reply",
        ]
        if any(b in lower_subject for b in blocked_subjects):
            logger.info(f"FILTERED OUT: Matches blocked subject ({subject})")
            return None

        # Only accept emails that look like real customer messages
        # If the email has no body and no attachment it is likely a system notification
        body_preview = ""
        for part in msg.walk() if msg.is_multipart() else [msg]:
            if part.get_content_type() == "text/plain":
                try:
                    body_preview = (part.get_payload(decode=True) or b"").decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )[:50]
                except Exception:
                    pass
                break
        if not body_preview.strip():
            logger.info(f"FILTERED OUT: Empty body ({subject})")
            return None

        body = ""
        attachment_filename = None
        attachment_b64 = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body += part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8', errors='replace')
                    except Exception:
                        pass
                elif content_type.startswith("image/") or content_type == "application/pdf":
                    if not attachment_filename: # get first
                        attachment_filename = part.get_filename() or "attachment"
                        raw_data = part.get_payload(decode=True)
                        if raw_data:
                            attachment_b64 = base64.b64encode(raw_data).decode('utf-8')
        else:
            if msg.get_content_type() == "text/plain":
                try:
                    body = msg.get_payload(decode=True).decode(msg.get_content_charset() or 'utf-8', errors='replace')
                except Exception:
                    pass

        if not body:
            body = "(No body text)"

        return {
            "id": message_id,
            "from_name": from_name,
            "from_email": from_email,
            "subject": subject,
            "body": body[:2000],
            "received_at": _parse_date(date_str),
            "source": "gmail",
            "attachment_filename": attachment_filename,
            "attachment_base64": attachment_b64,
            "_imap_uid": imap_uid # store for mark_as_read later if needed
        }
    except Exception as e:
        logger.warning(f"Failed to parse IMAP message: {e}")
        return None

def _parse_date(date_str: str) -> str:
    try:
        return parsedate_to_datetime(date_str).isoformat()
    except Exception:
        return "2026-09-10T00:00:00+00:00"

def create_gmail_draft(to_email: str, subject: str, html_body: str, message_id: str, attachment_paths: list[str] = None) -> bool:
    """
    Write the drafted reply as a Gmail Draft — NEVER auto-sends.
    Returns True on success.
    """
    try:
        import time
        import mimetypes
        import os
        from email.message import EmailMessage
        
        mail = _get_imap_connection()
        if not mail:
            return False

        msg = EmailMessage()
        msg["To"] = to_email
        msg["From"] = settings.GMAIL_ADDRESS
        msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        
        # Format properly for threading
        formatted_msg_id = f"<{message_id}>" if not message_id.startswith("<") else message_id
        msg["In-Reply-To"] = formatted_msg_id
        msg["References"] = formatted_msg_id
        
        # Add X-Unsent header to mark it as a draft in standard mail clients
        msg["X-Unsent"] = "1"
        
        # Start with a plain text fallback
        import re
        plain_text = re.sub(r'<[^>]+>', '', html_body)
        msg.set_content(plain_text)
        
        # Add the HTML version
        msg.add_alternative(html_body, subtype='html')
        
        # Add attachments if any (this automatically converts msg to multipart/mixed)
        if attachment_paths:
            for path in attachment_paths:
                if not os.path.exists(path):
                    continue
                ctype, encoding = mimetypes.guess_type(path)
                if ctype is None or encoding is not None:
                    ctype = 'application/octet-stream'
                maintype, subtype = ctype.split('/', 1)
                with open(path, 'rb') as f:
                    msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(path))

        # Append to [Gmail]/Drafts
        # Need to use correct draft folder name, usually '[Gmail]/Drafts' but could vary by language
        date_time = imaplib.Time2Internaldate(time.time())
        status, response = mail.append('"[Gmail]/Drafts"', '(\Draft)', date_time, msg.as_bytes())
        mail.logout()
        
        if status == "OK":
            logger.info(f"Gmail Draft created for {to_email}")
            return True
        else:
            logger.error(f"Failed to append draft: {response}")
            return False
    except Exception as e:
        logger.error(f"Failed to create Gmail Draft: {e}")
        return False

def send_email(to_email: str, subject: str, html_body: str, message_id: str, attachment_paths: list[str] = None) -> bool:
    """Send an email immediately using SMTP."""
    try:
        import smtplib
        import mimetypes
        import os
        from email.message import EmailMessage
        import re
        
        if not settings.GMAIL_ADDRESS or not settings.GMAIL_APP_PASSWORD:
            return False
            
        msg = EmailMessage()
        msg["To"] = to_email
        msg["From"] = settings.GMAIL_ADDRESS
        msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        
        # Format properly for threading
        formatted_msg_id = f"<{message_id}>" if not message_id.startswith("<") else message_id
        msg["In-Reply-To"] = formatted_msg_id
        msg["References"] = formatted_msg_id
        
        plain_text = re.sub(r'<[^>]+>', '', html_body)
        msg.set_content(plain_text)
        msg.add_alternative(html_body, subtype='html')
        
        if attachment_paths:
            for path in attachment_paths:
                if not os.path.exists(path):
                    continue
                ctype, encoding = mimetypes.guess_type(path)
                if ctype is None or encoding is not None:
                    ctype = 'application/octet-stream'
                maintype, subtype = ctype.split('/', 1)
                with open(path, 'rb') as f:
                    msg.add_attachment(f.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(path))
        
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
            server.send_message(msg)
            
        logger.info(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email via SMTP: {e}")
        return False

def mark_as_read(message_id: str, imap_uid: str = None):
    """Mark a message as seen via IMAP."""
    try:
        mail = _get_imap_connection()
        if not mail:
            return
            
        mail.select("INBOX")
        
        # If we have the exact uid from fetch, use it. Otherwise search by Message-ID.
        target_num = None
        if not imap_uid:
            # Search by Message-ID
            status, response = mail.search(None, f'(HEADER Message-ID "{message_id}")')
            if status == "OK" and response[0]:
                target_num = response[0].split()[0]
        else:
            target_num = imap_uid.encode('utf-8')
            
        if target_num:
            mail.store(target_num, '+FLAGS', '\\Seen')
            logger.info(f"Marked message {message_id} as read")
            
        mail.logout()
    except Exception as e:
        logger.warning(f"Could not mark message as read: {e}")
