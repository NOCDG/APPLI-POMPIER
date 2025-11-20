# app/core/email_utils.py
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from dotenv import load_dotenv
import os

load_dotenv()

conf = ConnectionConfig(
    MAIL_USERNAME=os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD=os.getenv("MAIL_PASSWORD"),
    MAIL_FROM=os.getenv("MAIL_FROM"),
    MAIL_PORT=int(os.getenv("MAIL_PORT", "587")),
    MAIL_SERVER=os.getenv("MAIL_SERVER"),
    MAIL_FROM_NAME=os.getenv("MAIL_FROM_NAME", "FEUILLE_GARDE"),
    # fastapi-mail récent n'accepte plus MAIL_TLS / MAIL_SSL, mais
    # MAIL_STARTTLS / MAIL_SSL_TLS → on mappe sur tes variables existantes
    MAIL_STARTTLS=(os.getenv("MAIL_TLS", "True") == "True"),
    MAIL_SSL_TLS=(os.getenv("MAIL_SSL", "False") == "True"),
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True,
)


async def send_email(
    subject: str,
    recipients: list[str],
    body: str,
    html: bool = False,
):
    """
    Envoie un email via FastAPI-Mail.

    - subject : sujet
    - recipients : liste d'adresses
    - body : texte ou HTML
    - html : True -> body est du HTML, False -> texte brut
    """
    message = MessageSchema(
        subject=subject,
        recipients=recipients,
        body=body,
        subtype="html" if html else "plain",
    )

    fm = FastMail(conf)
    await fm.send_message(message)
