from pydantic import BaseModel, Field
from typing import List, Optional

class MailTemplates(BaseModel):
    admin_validation_subject: str = "Validation feuille de garde – {{mois}} – {{equipe}}"
    admin_validation_html: str = "<p>La feuille du mois de <b>{{mois}}</b> a été validée par <b>{{validateur}}</b> pour l’équipe <b>{{equipe}}</b>.</p>"
    user_validation_subject: str = "Vos gardes – {{mois}} – {{equipe}}"
    user_validation_html: str = "<p>Bonjour {{prenom}} {{nom}},</p><p>Votre planning du mois de <b>{{mois}}</b> est validé.</p><p>{{tableau_gardes}}</p>"

class AppSettings(BaseModel):
    # DB
    POSTGRES_DB: str = "feuillegarde"
    POSTGRES_USER: str = "pompier"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Réseau / sécurité
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:5173"])
    BACKEND_PORT: int = 8000
    FRONTEND_PORT: int = 8080
    TZ: str = "Europe/Paris"
    JWT_SECRET: str = "CHANGE_ME"
    VITE_API_URL: str = "http://localhost:8000"

    # SMTP
    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = ""
    MAIL_FROM_NAME: str = "GARDE SPV - CSP SAINT-LÔ"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "smtp.gmail.com"
    MAIL_TLS: bool = True
    MAIL_SSL: bool = False

    # 📩 Adresse de notif à la validation
    MAIL_NOTIFY_TO: Optional[str] = None

    # Templates
    mail_templates: MailTemplates = Field(default_factory=MailTemplates)
