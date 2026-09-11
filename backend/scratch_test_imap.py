import sys
import os
sys.path.insert(0, r"c:\Users\tanmay\Documents\CS_Assistant\backend")

from app.core.config import settings
import imaplib
import email

def test():
    print(f"Connecting to {settings.GMAIL_ADDRESS}...")
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
    print("Logged in!")
    status, messages = mail.select("INBOX")
    print(f"Select INBOX status: {status}, Total messages: {messages[0].decode()}")
    
    status, response = mail.search(None, "UNSEEN")
    print(f"Search UNSEEN status: {status}, response: {response}")
    
    if response[0]:
        print(f"Unseen messages found: {response[0].split()}")
    else:
        print("No unseen messages.")
        
    mail.logout()

if __name__ == "__main__":
    test()
