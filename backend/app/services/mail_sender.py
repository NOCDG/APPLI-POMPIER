import smtplib, ssl
from email.message import EmailMessage
from typing import Optional
from app.schemas.settings import AppSettings


def send_test_email(settings: AppSettings, to_email: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = "Test SMTP – FEUILLE GARDE"
    msg["From"] = f'{settings.MAIL_FROM_NAME} <{settings.MAIL_FROM or settings.MAIL_USERNAME}>'
    msg["To"] = to_email
    msg.set_content("Mail de test en texte brut.")
    msg.add_alternative("""\
<html>
  <body style="font-family:Roboto,Arial,sans-serif;background:#0b0f20;color:#e9eeff;padding:16px">
    <div style="max-width:520px;margin:auto;background:#0d1226;border:1px solid #2e3a66;border-radius:12px;overflow:hidden">
      <div style="padding:16px 18px;background:#121a2f;border-bottom:1px solid #2e3a66">
        <h2 style="margin:0;color:#eaf1ff">Test SMTP ✅</h2>
      </div>
      <div style="padding:18px">
        <p>Si vous recevez cet e-mail, la configuration SMTP fonctionne.</p>
        <ul>
          <li>Serveur : <b>{server}</b></li>
          <li>Port : <b>{port}</b></li>
          <li>TLS : <b>{tls}</b> – SSL : <b>{ssl}</b></li>
          <li>Expéditeur : <b>{sender}</b></li>
        </ul>
      </div>
    </div>
  </body>
</html>
""".format(
        server=settings.MAIL_SERVER,
        port=settings.MAIL_PORT,
        tls=str(settings.MAIL_TLS),
        ssl=str(settings.MAIL_SSL),
        sender=(settings.MAIL_FROM or settings.MAIL_USERNAME),
    ), subtype="html")

    # Connexion SMTP
    if settings.MAIL_SSL:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.MAIL_SERVER, settings.MAIL_PORT, context=context) as smtp:
            if settings.MAIL_USERNAME:
                smtp.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(settings.MAIL_SERVER, settings.MAIL_PORT) as smtp:
            if settings.MAIL_TLS:
                smtp.starttls(context=ssl.create_default_context())
            if settings.MAIL_USERNAME:
                smtp.login(settings.MAIL_USERNAME, settings.MAIL_PASSWORD)
            smtp.send_message(msg)
