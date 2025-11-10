from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import load_dotenv
import os

load_dotenv()

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT")),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME"),
    MAIL_TLS=os.getenv("MAIL_TLS") == "True",
    MAIL_SSL=os.getenv("MAIL_SSL") == "True",
    USE_CREDENTIALS=True,
)

async def send_email(subject: str, recipients: list[str], body: str, html: bool = False):
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype="html" if html else "plain"
    )

    fm = FastMail(conf)
    await fm.send_message(message)
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import load_dotenv
import os

load_dotenv()

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT")),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME"),
    MAIL_TLS=os.getenv("MAIL_TLS") == "True",
    MAIL_SSL=os.getenv("MAIL_SSL") == "True",
    USE_CREDENTIALS=True,
)

async def send_email(subject: str, recipients: list[str], body: str, html: bool = False):
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype="html" if html else "plain"
    )

    fm = FastMail(conf)
    await fm.send_message(message)
