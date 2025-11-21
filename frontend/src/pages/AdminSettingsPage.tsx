import React, { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { RoleGuard } from "../auth/guards";
import HtmlEditor from "../components/HtmlEditor";
import {
  getAppSettings, saveAppSettings, testEmail,
  type AppSettings, type MailTemplates
} from "../api";
import "./admin-settings.css";

const EMPTY_SETTINGS: AppSettings = {
  POSTGRES_DB: "",
  POSTGRES_USER: "",
  POSTGRES_PASSWORD: "",
  POSTGRES_HOST: "localhost",
  POSTGRES_PORT: 5432,
  CORS_ORIGINS: [],
  BACKEND_PORT: 8000,
  FRONTEND_PORT: 8080,
  TZ: "Europe/Paris",
  JWT_SECRET: "",
  MAIL_USERNAME: "",
  MAIL_PASSWORD: "",
  MAIL_FROM: "",
  MAIL_PORT: 587,
  MAIL_SERVER: "smtp.gmail.com",
  MAIL_FROM_NAME: "GARDE SPV - CSP SAINT-LÔ",
  MAIL_TLS: true,
  MAIL_SSL: false,
  VITE_API_URL: "https://pompier.gandour.org/api",
  mail_templates: {
    admin_validation_subject: "Validation feuille de garde – {{mois}} – {{equipe}}",
    admin_validation_html: "<p>La feuille du mois de <b>{{mois}}</b> a été validée par <b>{{validateur}}</b> pour l’équipe <b>{{equipe}}</b>.</p>",
    user_validation_subject: "Vos gardes – {{mois}} – {{equipe}}",
    user_validation_html: "<p>Bonjour {{prenom}} {{nom}},</p><p>Votre planning du mois de <b>{{mois}}</b> est validé.</p><p>{{tableau_gardes}}</p>",
  },
};

export default function AdminSettingsPage() {
  const { hasAnyRole } = useAuth();
  const allowed = hasAnyRole("ADMIN");
  const [settings, setSettings] = useState<AppSettings>(EMPTY_SETTINGS);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testTo, setTestTo] = useState("");

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const s = await getAppSettings();
        setSettings(normalizeSettings(s));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function normalizeSettings(s: any): AppSettings {
    const clone = { ...EMPTY_SETTINGS, ...s };
    // CORS_ORIGINS peut venir en string / JSON string / array -> normalise en array<string>
    if (typeof clone.CORS_ORIGINS === "string") {
      const val = clone.CORS_ORIGINS.trim();
      if (val.startsWith("["))
        try { clone.CORS_ORIGINS = JSON.parse(val); } catch { clone.CORS_ORIGINS = [val]; }
      else clone.CORS_ORIGINS = val ? val.split(",").map((x: string) => x.trim()).filter(Boolean) : [];
    }
    clone.POSTGRES_PORT = Number(clone.POSTGRES_PORT || 5432);
    clone.BACKEND_PORT  = Number(clone.BACKEND_PORT || 8000);
    clone.FRONTEND_PORT = Number(clone.FRONTEND_PORT || 8080);
    clone.MAIL_PORT     = Number(clone.MAIL_PORT || 587);
    clone.MAIL_TLS = !!(clone.MAIL_TLS === true || String(clone.MAIL_TLS).toLowerCase() === "true");
    clone.MAIL_SSL = !!(clone.MAIL_SSL === true || String(clone.MAIL_SSL).toLowerCase() === "true");
    return clone;
  }

  const update = (patch: Partial<AppSettings>) => setSettings(prev => ({ ...prev, ...patch }));
  const updateTpl = (patch: Partial<MailTemplates>) =>
    setSettings(prev => ({ ...prev, mail_templates: { ...prev.mail_templates, ...patch }}));

  async function onSave() {
    setSaving(true);
    try {
      await saveAppSettings(settings);
      const fresh = await getAppSettings();     // ← rechargement pour l’état source de vérité
      setSettings(normalizeSettings(fresh));
      alert("Paramètres enregistrés ✅");
    } catch (e:any) {
      alert(e?.message || "Erreur d’enregistrement");
    } finally {
      setSaving(false);
    }
  }

  async function onTestEmail() {
    const to = testTo.trim();
    if (!to) return alert("Renseigne un destinataire test.");
    try {
      await testEmail(to);
      alert("Mail de test envoyé ✅");
    } catch (e: any) {
      alert(e?.message || "Erreur lors de l’envoi du mail de test");
    }
  }

  const corsStr = useMemo(() => JSON.stringify(settings.CORS_ORIGINS || []), [settings.CORS_ORIGINS]);

  if (!allowed) return (
    <div className="pl-container">
      <h2 className="pl-title">⚙️ Paramètres</h2>
      <div className="pl-empty">Accès réservé aux administrateurs.</div>
    </div>
  );

  return (
    <div className="pl-container">
      <h2 className="pl-title">⚙️ Paramètres de l’application</h2>

      {loading ? <div className="pl-muted">Chargement…</div> : (
        <>
          {/* DB */}
          <fieldset className="as-card">
            <legend>🗄️ Base de données (PostgreSQL)</legend>
            <div className="as-grid">
              <label>POSTGRES_DB
                <input className="as-input" value={settings.POSTGRES_DB} onChange={e=>update({POSTGRES_DB:e.target.value})}/>
              </label>
              <label>POSTGRES_USER
                <input className="as-input" value={settings.POSTGRES_USER} onChange={e=>update({POSTGRES_USER:e.target.value})}/>
              </label>
              <label>POSTGRES_PASSWORD
                <input className="as-input" type="password" value={settings.POSTGRES_PASSWORD} onChange={e=>update({POSTGRES_PASSWORD:e.target.value})}/>
              </label>
              <label>POSTGRES_HOST
                <input className="as-input" value={settings.POSTGRES_HOST} onChange={e=>update({POSTGRES_HOST:e.target.value})}/>
              </label>
              <label>POSTGRES_PORT
                <input className="as-input" type="number" value={settings.POSTGRES_PORT} onChange={e=>update({POSTGRES_PORT:Number(e.target.value)})}/>
              </label>
            </div>
          </fieldset>

          {/* Réseau / Sécurité */}
          <fieldset className="as-card">
            <legend>🌐 Réseau & sécurité</legend>
            <div className="as-grid">
              <label>BACKEND_PORT
                <input className="as-input" type="number" value={settings.BACKEND_PORT} onChange={e=>update({BACKEND_PORT:Number(e.target.value)})}/>
              </label>
              <label>FRONTEND_PORT
                <input className="as-input" type="number" value={settings.FRONTEND_PORT} onChange={e=>update({FRONTEND_PORT:Number(e.target.value)})}/>
              </label>
              <label>VITE_API_URL
                <input className="as-input" value={settings.VITE_API_URL} onChange={e=>update({VITE_API_URL:e.target.value})}/>
              </label>
              <label>TZ
                <input className="as-input" value={settings.TZ} onChange={e=>update({TZ:e.target.value})}/>
              </label>
              <label>JWT_SECRET
                <input className="as-input" type="password" value={settings.JWT_SECRET} onChange={e=>update({JWT_SECRET:e.target.value})}/>
              </label>
              <label>CORS_ORIGINS (JSON array)
                <textarea className="as-textarea" value={corsStr}
                  onChange={e=>{
                    try { update({ CORS_ORIGINS: JSON.parse(e.target.value) }) }
                    catch { /* ignore while typing */ }
                  }}/>
              </label>
            </div>
          </fieldset>

          {/* Mail */}
          <fieldset className="as-card">
            <legend>✉️ Mail (SMTP)</legend>
            <div className="as-grid">
              <label>MAIL_USERNAME
                <input className="as-input" value={settings.MAIL_USERNAME} onChange={e=>update({MAIL_USERNAME:e.target.value})}/>
              </label>
              <label>MAIL_PASSWORD
                <input className="as-input" type="password" value={settings.MAIL_PASSWORD} onChange={e=>update({MAIL_PASSWORD:e.target.value})}/>
              </label>
              <label>MAIL_FROM
                <input className="as-input" value={settings.MAIL_FROM} onChange={e=>update({MAIL_FROM:e.target.value})}/>
              </label>
              <label>MAIL_FROM_NAME
                <input className="as-input" value={settings.MAIL_FROM_NAME} onChange={e=>update({MAIL_FROM_NAME:e.target.value})}/>
              </label>
              <label>MAIL_NOTIFY_TO (notification validation)
                <input
                  className="as-input"
                  value={settings.MAIL_NOTIFY_TO || ""}
                  onChange={e => update({ MAIL_NOTIFY_TO: e.target.value })}
                  placeholder="ex: chef.de.centre@exemple.fr"
                />
              </label>
              <label>MAIL_SERVER
                <input className="as-input" value={settings.MAIL_SERVER} onChange={e=>update({MAIL_SERVER:e.target.value})}/>
              </label>
              <label>MAIL_PORT
                <input className="as-input" type="number" value={settings.MAIL_PORT} onChange={e=>update({MAIL_PORT:Number(e.target.value)})}/>
              </label>
              <label>MAIL_TLS
                <select className="as-input" value={settings.MAIL_TLS ? "true":"false"} onChange={e=>update({MAIL_TLS: e.target.value==="true"})}>
                  <option value="true">true</option><option value="false">false</option>
                </select>
              </label>
              <label>MAIL_SSL
                <select className="as-input" value={settings.MAIL_SSL ? "true":"false"} onChange={e=>update({MAIL_SSL: e.target.value==="true"})}>
                  <option value="true">true</option><option value="false">false</option>
                </select>
              </label>
            </div>

            <div className="as-testmail">
              <input className="as-input" placeholder="Adresse test…" value={testTo} onChange={e=>setTestTo(e.target.value)}/>
              <button className="pl-btn" onClick={onTestEmail}>📬 Envoyer un mail de test</button>
            </div>
          </fieldset>

          {/* Templates mail */}
          <fieldset className="as-card">
            <legend>🧩 Modèles d’e-mails</legend>
            <p className="pl-muted" style={{ marginTop: -6 }}>
            Variables disponibles :
            {' '}
            <code>{"{{mois}}"}</code>, <code>{"{{equipe}}"}</code>, <code>{"{{validateur}}"}</code>,
            {' '}
            <code>{"{{prenom}}"}</code>, <code>{"{{nom}}"}</code>, <code>{"{{tableau_gardes}}"}</code> (HTML).
            </p>
            <div className="as-grid">
              <label>Sujet (admin)
                <input className="as-input"
                  value={settings.mail_templates.admin_validation_subject}
                  onChange={e=>updateTpl({admin_validation_subject:e.target.value})}/>
              </label>
              <label>HTML (admin)
                <textarea className="as-textarea code"
                  value={settings.mail_templates.admin_validation_html}
                  onChange={e=>updateTpl({admin_validation_html:e.target.value})}/>
              </label>

              <label>Sujet (agent)
                <input className="as-input"
                  value={settings.mail_templates.user_validation_subject}
                  onChange={e=>updateTpl({user_validation_subject:e.target.value})}/>
              </label>
              <label>HTML (agent)
                <textarea className="as-textarea code"
                  value={settings.mail_templates.user_validation_html}
                  onChange={e=>updateTpl({user_validation_html:e.target.value})}/>
              </label>
            </div>
          </fieldset>

          <div style={{display:"flex", gap:8, marginTop:12}}>
            <button className="pl-btn" onClick={onSave} disabled={saving}>
              💾 Enregistrer
            </button>
          </div>
        </>
      )}
    </div>
  );
}
