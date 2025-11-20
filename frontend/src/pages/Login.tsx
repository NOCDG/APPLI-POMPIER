import { useEffect, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import { Link } from "react-router-dom";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [remember, setRemember] = useState(false);
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);

  // Pré-remplir l'email si mémorisé
  useEffect(() => {
    const saved = localStorage.getItem("remember_email");
    if (saved) {
      setEmail(saved);
      setRemember(true);
    }
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      await login(email.trim(), password);
      if (remember) localStorage.setItem("remember_email", email.trim());
      else localStorage.removeItem("remember_email");
      // redirection gérée par PrivateRoute après succès
    } catch (e: any) {
      setErr(e?.message || "Échec de la connexion");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="brand">
          <div className="brand-badge">🚒</div>
          <div>
            <h1>Planification Garde SPV</h1>
            <p className="muted">CIS Saint-Lô</p>
          </div>
        </div>

        <form onSubmit={submit} className="form">
          <label className="field">
            <span>Email</span>
            <div className="control">
              <input
                type="email"
                placeholder="prenom.nom@sdis50.fr"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoFocus
                required
              />
            </div>
          </label>

          <label className="field">
            <span>Mot de passe</span>
            <div className="control control--with-button">
              <input
                type={showPwd ? "text" : "password"}
                placeholder="••••••••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="ghost"
                onClick={() => setShowPwd((s) => !s)}
                aria-label={showPwd ? "Masquer le mot de passe" : "Afficher le mot de passe"}
              >
                {showPwd ? "🙈" : "👁️"}
              </button>
            </div>
          </label>

          <label className="remember">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            <span>Mémoriser l’email</span>
          </label>

          {err && <div className="alert">{err}</div>}

          <button className="btn btn-primary wide" disabled={loading}>
            {loading ? <span className="spinner" /> : "Se connecter"}
          </button>
        </form>

        <div className="login-footer">
              <p className="login-forgot">
              <Link to="/forgot-password">Mot de passe oublié ?</Link>
            </p>
          <span className="muted">v1.0 · FEUILLE_GARDE</span>
        </div>
      </div>
    </div>
  );
}
