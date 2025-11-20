# app/core/mailer.py
from __future__ import annotations
import os
import smtplib
from email.utils import formataddr
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable, Optional
from sqlalchemy.orm import Session

try:
    # si ton modèle Alembic existe
    from app.db.models import AppSetting  # type: ignore
except Exception:
    AppSetting = None  # le mailer restera fonctionnel via os.environ


# ——————————————————————————————————————
# Helpers lecture settings (DB -> ENV -> défaut)
# ——————————————————————————————————————
def _get_db_setting(db: Optional[Session], key: str) -> Optional[str]:
    if db is None or AppSetting is None:
        return None
    row = db.query(AppSetting).filter(AppSetting.key == key).first()
    if not row:
        return None
    val = row.value
    # value peut être texte ou JSON; on convertit en str simple quand utile
    if isinstance(val, (dict, list)):
        # pas utile ici; on retourne None pour forcer env
        return None
    return str(val) if val is not None else None


def get_setting(db: Optional[Session], key: str, default: Optional[str] = None) -> Optional[str]:
    return _get_db_setting(db, key) or os.getenv(key) or default


# ——————————————————————————————————————
# Const d’expo pour compat (utilisée par gardes.py)
# NB: on ne tape pas la DB au import. Juste un défaut lisible.
# ——————————————————————————————————————
MAIL_FROM_NAME = os.getenv("MAIL_FROM_NAME", "GARDE SPV - CSP SAINT-LÔ")


# ——————————————————————————————————————
# Envoi d’e-mail HTML
# ——————————————————————————————————————
def send_mail(
    to: str | Iterable[str],
    subject: str,
    html: str,
    *,
    db: Optional[Session] = None,
    reply_to: Optional[str] = None,
) -> None:
    """
    Envoie un e-mail HTML via SMTP (TLS recommandé).
    Lit d’abord les paramètres en BDD (table app_settings), sinon variables d’environnement.
    """
    username = get_setting(db, "MAIL_USERNAME", "")
    password = get_setting(db, "MAIL_PASSWORD", "")
    mail_from = get_setting(db, "MAIL_FROM", username) or ""
    mail_from_name = get_setting(db, "MAIL_FROM_NAME", MAIL_FROM_NAME) or MAIL_FROM_NAME
    server_host = get_setting(db, "MAIL_SERVER", "smtp.gmail.com") or "smtp.gmail.com"
    server_port = int(get_setting(db, "MAIL_PORT", "587") or "587")
    use_tls = (get_setting(db, "MAIL_TLS", "True") or "True").lower() == "true"
    use_ssl = (get_setting(db, "MAIL_SSL", "False") or "False").lower() == "true"

    if isinstance(to, str):
        recipients = [to]
    else:
        recipients = list(to)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((mail_from_name, mail_from))
    msg["To"] = ", ".join(recipients)
    if reply_to:
        msg["Reply-To"] = reply_to

    msg.attach(MIMEText(html, "html", "utf-8"))

    if use_ssl:
        with smtplib.SMTP_SSL(server_host, server_port) as smtp:
            if username and password:
                smtp.login(username, password)
            smtp.sendmail(mail_from, recipients, msg.as_string())
    else:
        with smtplib.SMTP(server_host, server_port) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.sendmail(mail_from, recipients, msg.as_string())


# ——————————————————————————————————————
# Templates / utilitaires
# ——————————————————————————————————————
def build_validation_html(mois_label: str, equipe_label: str, validateur: str) -> str:
    """Petit gabarit HTML propre pour le mail d’info admin."""
    return f"""
<!doctype html>
<html lang="fr">
  <body style="margin:0;padding:0;background:#0b1020;font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;color:#eaf1ff;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#0b1020;padding:24px 0;">
      <tr><td align="center">
        <table role="presentation" width="620" cellspacing="0" cellpadding="0" style="background:#0d1226;border:1px solid #243166;border-radius:12px;overflow:hidden">
          <tr>
            <td style="background:#1a2c6e;color:#fff;padding:18px 20px;font-weight:700;font-size:16px;">
              GARDE SPV – Confirmation de validation
            </td>
          </tr>
          <tr>
            <td style="padding:20px">
              <p style="margin:0 0 8px 0;font-size:15px;color:#b9c6ff;">Bonjour,</p>
              <p style="margin:0 0 14px 0;font-size:15px;">
                La feuille de garde du mois de <b>{mois_label}</b> a été <b>validée</b> pour l’équipe <b>{equipe_label}</b>.
              </p>
              <table role="presentation" cellspacing="0" cellpadding="0" style="margin:14px 0;border-collapse:separate;border-spacing:0 8px;font-size:14px;">
                <tr>
                  <td style="color:#9fb2ff;padding-right:12px;">Équipe :</td>
                  <td style="color:#eaf1ff;"><b>{equipe_label}</b></td>
                </tr>
                <tr>
                  <td style="color:#9fb2ff;padding-right:12px;">Mois :</td>
                  <td style="color:#eaf1ff;"><b>{mois_label}</b></td>
                </tr>
                <tr>
                  <td style="color:#9fb2ff;padding-right:12px;">Validée par :</td>
                  <td style="color:#eaf1ff;"><b>{validateur}</b></td>
                </tr>
              </table>
              <p style="margin:14px 0 0 0;font-size:14px;color:#9fb2ff;">Bien cordialement,</p>
              <p style="margin:0;font-size:14px;">{MAIL_FROM_NAME}</p>
            </td>
          </tr>
          <tr>
            <td style="padding:12px 20px;background:#0b0f20;color:#8ea0d9;font-size:12px;">
              Ce message est envoyé automatiquement par l’application de gestion des feuilles de garde.
            </td>
          </tr>
        </table>
      </td></tr>
    </table>
  </body>
</html>
""".strip()

def send_email(
    to: str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
) -> None:
    """
    Wrapper pour compatibilité avec les routes d'auth / reset password.

    - `text_body` : version texte (pour les clients qui ne lisent pas le HTML)
    - `html_body` : version HTML (si fournie, on privilégie le HTML)

    Comme le reste de ton appli utilise `send_mail(to, subject, html_body)`,
    on réutilise cette fonction ici.
    """
    body = html_body or text_body
    # ⚠️ on suppose que send_mail(to, subject, body_html) existe déjà
    send_mail(to, subject, body)