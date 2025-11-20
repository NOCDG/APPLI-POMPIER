import React, { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { resetPassword } from "../api";

const ResetPassword: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (!token) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <p>Token de réinitialisation invalide ou manquant.</p>
          <Link to="/login">Retour à la connexion</Link>
        </div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirm) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }

    if (password.length < 8) {
      setError("Le mot de passe doit contenir au moins 8 caractères.");
      return;
    }

    setLoading(true);
    try {
      await resetPassword(token, password);
      setDone(true);
    } catch (err) {
      console.error(err);
      setError(
        "Erreur lors de la réinitialisation. Le lien a peut-être expiré."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h2>Choisissez un nouveau mot de passe</h2>

        {done ? (
          <>
            <p>Votre mot de passe a été mis à jour avec succès.</p>
            <Link to="/login">Retour à la connexion</Link>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="auth-form">
            <label>
              Nouveau mot de passe :
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
            </label>

            <label>
              Confirmer le mot de passe :
              <input
                type="password"
                value={confirm}
                onChange={e => setConfirm(e.target.value)}
                required
              />
            </label>

            {error && <p className="auth-error">{error}</p>}

            <button type="submit" disabled={loading}>
              {loading ? "En cours..." : "Valider"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default ResetPassword;
