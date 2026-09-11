import asyncio
import smtplib
from email.message import EmailMessage
from app.core.config import settings

async def send_test():
    msg = EmailMessage()
    msg.set_content("Hi, my order 101 arrived broken. Can I get a replacement?")
    msg["Subject"] = "Broken order 101"
    msg["From"] = settings.GMAIL_ADDRESS
    msg["To"] = settings.GMAIL_ADDRESS

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(settings.GMAIL_ADDRESS, settings.GMAIL_APP_PASSWORD)
        server.send_message(msg)
    print("Test email sent!")

if __name__ == "__main__":
    asyncio.run(send_test())
