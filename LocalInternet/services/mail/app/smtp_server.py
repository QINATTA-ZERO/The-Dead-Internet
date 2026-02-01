import asyncio
from aiosmtpd.controller import Controller
from email.parser import BytesParser
from email.policy import default
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
import os
import sys

# Import models from the app directory
sys.path.append("/app")
import models

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/psx_core")
engine = create_engine(DATABASE_URL)

class MailHandler:
    async def handle_DATA(self, server, session, envelope):
        print(f"Receiving mail from {envelope.mail_from}")
        peer = session.peer
        data = envelope.content
        msg = BytesParser(policy=default).parsebytes(data)
        
        subject = msg.get('subject', '(No Subject)')
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    body = part.get_payload(decode=True).decode()
                    break
        else:
            body = msg.get_payload(decode=True).decode()

        # Save to DB
        with Session(engine) as db:
            for rcpt in envelope.rcpt_tos:
                # rcpt is likely user@mail.psx or user@psx.local
                username = rcpt.split('@')[0]
                new_email = models.Email(
                    sender=envelope.mail_from,
                    recipient=username,
                    subject=subject,
                    body=body
                )
                db.add(new_email)
            db.commit()
        
        return '250 Message accepted for delivery'

if __name__ == "__main__":
    handler = MailHandler()
    controller = Controller(handler, hostname='0.0.0.0', port=25)
    print("Starting SMTP server on port 25...")
    controller.start()
    
    # Keep it running
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        controller.stop()
