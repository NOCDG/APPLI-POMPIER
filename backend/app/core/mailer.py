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

# ——————————————————————————————————————
# Base HTML commune
# ——————————————————————————————————————
def _html_base(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="fr">
<body style="margin:0;padding:0;background:#0b1020;font-family:system-ui,Segoe UI,Roboto,Arial,sans-serif;color:#eaf1ff;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#0b1020;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="620" cellspacing="0" cellpadding="0"
             style="background:#0d1226;border:1px solid #243166;border-radius:12px;overflow:hidden">
        <tr><td style="background:#1a2c6e;color:#fff;padding:18px 20px;font-weight:700;font-size:16px;">{title}</td></tr>
        <tr><td style="padding:20px">{body}</td></tr>
        <tr><td style="padding:12px 20px;background:#0b0f20;color:#8ea0d9;font-size:12px;">
          Ce message est envoyé automatiquement par l'application de gestion des feuilles de garde.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>""".strip()


def _table_3col(rows: list[tuple[str, str, str]]) -> str:
    """Table gardes 3 colonnes : Date | Slot | Piquet"""
    cells = "".join(
        f'<tr>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #1e2a4a;color:#c8d8ff">{d}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #1e2a4a;color:#c8d8ff">{s}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #1e2a4a;color:#eaf1ff">{p}</td>'
        f'</tr>'
        for d, s, p in rows
    )
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"'
        ' style="border-collapse:collapse;font-size:14px;background:#0d1530;border-radius:8px;overflow:hidden;margin:10px 0 14px">'
        '<thead><tr>'
        '<th style="padding:8px 10px;text-align:left;background:#1a2c6e;color:#c8d8ff;font-weight:600">Date</th>'
        '<th style="padding:8px 10px;text-align:left;background:#1a2c6e;color:#c8d8ff;font-weight:600">Slot</th>'
        '<th style="padding:8px 10px;text-align:left;background:#1a2c6e;color:#c8d8ff;font-weight:600">Piquet</th>'
        f'</tr></thead><tbody>{cells}</tbody></table>'
    )


def _table_4col(rows: list[tuple[str, str, str, str]]) -> str:
    """Table gardes 4 colonnes : Date | Slot | Équipe | Piquet"""
    cells = "".join(
        f'<tr>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #1e2a4a;color:#c8d8ff">{d}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #1e2a4a;color:#c8d8ff">{s}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #1e2a4a;color:#c8d8ff">{e}</td>'
        f'<td style="padding:6px 10px;border-bottom:1px solid #1e2a4a;color:#eaf1ff">{p}</td>'
        f'</tr>'
        for d, s, e, p in rows
    )
    return (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0"'
        ' style="border-collapse:collapse;font-size:14px;background:#0d1530;border-radius:8px;overflow:hidden;margin:10px 0 14px">'
        '<thead><tr>'
        '<th style="padding:8px 10px;text-align:left;background:#1a2c6e;color:#c8d8ff;font-weight:600">Date</th>'
        '<th style="padding:8px 10px;text-align:left;background:#1a2c6e;color:#c8d8ff;font-weight:600">Slot</th>'
        '<th style="padding:8px 10px;text-align:left;background:#1a2c6e;color:#c8d8ff;font-weight:600">Équipe</th>'
        '<th style="padding:8px 10px;text-align:left;background:#1a2c6e;color:#c8d8ff;font-weight:600">Piquet</th>'
        f'</tr></thead><tbody>{cells}</tbody></table>'
    )


# ——————————————————————————————————————
# Template : validation → agent de l'équipe
# ——————————————————————————————————————
def build_html_agent_team(
    agent_fullname: str,
    mois_label: str,
    equipe_label: str,
    gardes_rows: list[tuple[str, str, str]],
) -> str:
    body = (
        f'<p style="margin:0 0 8px;font-size:15px;color:#b9c6ff">Bonjour {agent_fullname},</p>'
        f'<p style="margin:0 0 14px;font-size:15px">La feuille de garde de l\'équipe <b>{equipe_label}</b> '
        f'pour le mois de <b>{mois_label}</b> vient d\'être <b>validée</b>.</p>'
        f'<p style="margin:0 0 6px;font-size:14px;color:#9fb2ff">Vos gardes pour ce mois :</p>'
        f'{_table_3col(gardes_rows)}'
        f'<p style="margin:0 0 4px;font-size:14px;color:#9fb2ff">Bien cordialement,</p>'
        f'<p style="margin:0;font-size:14px">{MAIL_FROM_NAME}</p>'
    )
    return _html_base("GARDE SPV – Feuille de garde disponible", body)


# ——————————————————————————————————————
# Template : validation → agent hors équipe (monte)
# ——————————————————————————————————————
def build_html_agent_external(
    agent_fullname: str,
    mois_label: str,
    equipe_label: str,
    gardes_rows: list[tuple[str, str, str]],
) -> str:
    body = (
        f'<p style="margin:0 0 8px;font-size:15px;color:#b9c6ff">Bonjour {agent_fullname},</p>'
        f'<p style="margin:0 0 14px;font-size:15px">Vous avez été planifié pour <b>monter avec l\'équipe {equipe_label}</b> '
        f'pour le mois de <b>{mois_label}</b>.</p>'
        f'<p style="margin:0 0 6px;font-size:14px;color:#9fb2ff">Vos gardes avec cette équipe :</p>'
        f'{_table_3col(gardes_rows)}'
        f'<p style="margin:0 0 4px;font-size:14px;color:#9fb2ff">Bien cordialement,</p>'
        f'<p style="margin:0;font-size:14px">{MAIL_FROM_NAME}</p>'
    )
    return _html_base("GARDE SPV – Montée de garde", body)


# ——————————————————————————————————————
# Template : réinitialisation de mot de passe
# ——————————————————————————————————————
def build_html_reset_password(reset_link: str) -> str:
    body = (
        '<p style="margin:0 0 8px;font-size:15px;color:#b9c6ff">Bonjour,</p>'
        '<p style="margin:0 0 14px;font-size:15px">Vous avez demandé à réinitialiser votre mot de passe.</p>'
        '<table role="presentation" cellspacing="0" cellpadding="0" style="margin:16px 0">'
        '<tr><td style="border-radius:8px;background:#2a4cbf">'
        f'<a href="{reset_link}" style="display:inline-block;padding:12px 24px;color:#fff;'
        'font-size:14px;font-weight:600;text-decoration:none;border-radius:8px;">'
        'Réinitialiser mon mot de passe</a>'
        '</td></tr></table>'
        '<p style="margin:4px 0;font-size:13px;color:#8ea0d9">Ou copiez ce lien dans votre navigateur :</p>'
        f'<p style="margin:0 0 14px;font-size:12px;color:#a0b0d9;word-break:break-all">{reset_link}</p>'
        '<p style="margin:0 0 14px;font-size:13px;color:#8ea0d9">'
        'Ce lien est valable <b>30 minutes</b>. Si vous n\'êtes pas à l\'origine de cette demande, ignorez ce message.</p>'
        f'<p style="margin:0 0 4px;font-size:14px;color:#9fb2ff">Bien cordialement,</p>'
        f'<p style="margin:0;font-size:14px">{MAIL_FROM_NAME}</p>'
    )
    return _html_base("GARDE SPV – Réinitialisation de mot de passe", body)


# ——————————————————————————————————————
# Template : rappel mensuel (envoyé le 25)
# ——————————————————————————————————————
def build_html_monthly_reminder(
    agent_fullname: str,
    mois_label: str,
    gardes_rows: list[tuple[str, str, str, str]],  # (date, slot, equipe, piquet)
) -> str:
    warning = (
        '<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin:8px 0">'
        '<tr><td style="background:#2a1a3a;border:1px solid #5a3a7a;border-radius:8px;padding:12px 14px">'
        '<p style="margin:0;font-size:13px;color:#d4b8ff">'
        '⚠️ <b>Ce mail est envoyé sous réserve de modifications.</b><br>'
        'La feuille de garde n\'est peut-être pas encore validée définitivement. '
        'Des changements peuvent intervenir jusqu\'à la validation officielle par votre chef d\'équipe.'
        '</p></td></tr></table>'
    )
    body = (
        f'<p style="margin:0 0 8px;font-size:15px;color:#b9c6ff">Bonjour {agent_fullname},</p>'
        f'<p style="margin:0 0 14px;font-size:15px">Voici le récapitulatif de vos gardes pour le mois de <b>{mois_label}</b>.</p>'
        f'{_table_4col(gardes_rows)}'
        f'{warning}'
        f'<p style="margin:14px 0 4px;font-size:14px;color:#9fb2ff">Bien cordialement,</p>'
        f'<p style="margin:0;font-size:14px">{MAIL_FROM_NAME}</p>'
    )
    return _html_base(f"GARDE SPV – Vos gardes de {mois_label}", body)


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