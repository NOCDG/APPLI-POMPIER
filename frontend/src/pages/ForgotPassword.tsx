import React, { useState } from "react";
import { forgotPassword } from "../api";

const ForgotPassword: React.FC = () => {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await forgotPassword(email);
      setSent(true);
    } catch (err) {
      console.error(err);
      setError("Une erreur est survenue. Réessayez plus tard.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h2>Mot de passe oublié</h2>

        {sent ? (
          <p>
            Si cette adresse existe, un email de réinitialisation vous a été
            envoyé.
          </p>
        ) : (
          <form onSubmit={handleSubmit} className="auth-form">
            <label>
              Adresse email :
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
              />
            </label>

            {error && <p className="auth-error">{error}</p>}

            <button type="submit" disabled={loading}>
              {loading ? "Envoi..." : "Envoyer le lien"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
};

export default ForgotPassword;
