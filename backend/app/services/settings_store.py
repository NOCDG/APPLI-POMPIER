from typing import Any, Dict
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import AppSetting
from app.schemas.settings import AppSettings, MailTemplates

DEFAULTS = AppSettings()  # valeurs par défaut

def _to_dict(p: AppSettings) -> Dict[str, Any]:
    d = p.model_dump()
    return d

def _merge(base: dict, override: dict | None) -> dict:
    if not override:
        return base
    out = base.copy()
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out

def load_settings(db: Session) -> AppSettings:
    """Charge tous les settings depuis la table app_settings et merge avec DEFAULTS."""
    rows = db.scalars(select(AppSetting)).all()
    kv = {row.key: row.value for row in rows}

    # reconstruire un dict plat + sous-objets
    # mail_templates est un sous-objet
    mt = kv.get("mail_templates", None)
    merged = _merge(_to_dict(DEFAULTS), kv)
    if mt and isinstance(mt, dict):
        merged["mail_templates"] = _merge(DEFAULTS.mail_templates.model_dump(), mt)

    return AppSettings.model_validate(merged)

def save_settings(db: Session, payload: AppSettings) -> AppSettings:
    """Ecrase tous les champs présents dans payload (merge côté schéma/pydantic)."""
    data = payload.model_dump()
    # Séparer sous-objets
    mail_templates = data.pop("mail_templates", None)

    # upsert simples
    for k, v in data.items():
        _upsert(db, k, v)
    if mail_templates is not None:
        _upsert(db, "mail_templates", mail_templates)

    db.commit()
    return load_settings(db)

def patch_settings(db: Session, patch: dict) -> AppSettings:
    """Mise à jour partielle (utilisée par PUT /settings avec Partial[AppSettings])."""
    # protéger mail_templates si présent
    mt = patch.pop("mail_templates", None)

    for k, v in patch.items():
        _upsert(db, k, v)

    if mt is not None:
        # merge fin avec l’existant pour mail_templates
        current = get_value(db, "mail_templates") or {}
        if not isinstance(current, dict):
            current = {}
        current.update(mt)
        _upsert(db, "mail_templates", current)

    db.commit()
    return load_settings(db)

def get_value(db: Session, key: str):
    row = db.get(AppSetting, key)
    return row.value if row else None

def _upsert(db: Session, key: str, value: Any):
    row = db.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.add(AppSetting(key=key, value=value))
