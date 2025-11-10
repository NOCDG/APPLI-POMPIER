import React from "react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

export default function Nav() {
  const { user, logout, hasAnyRole } = useAuth();

  // Helper pour simplifier les vérifications de rôle
  const can = (...roles: string[]) => hasAnyRole(...roles);

  const item = (to: string, label: string) => (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `px-3 py-2 rounded-xl ${
          isActive ? "bg-[#1b2544] text-white" : "bg-[#121a2f] text-[#eaf1ff]"
        }`
      }
      style={{ textDecoration: "none" }}
    >
      {label}
    </NavLink>
  );

  return (
    <nav
      style={{
        display: "flex",
        gap: 8,
        flexWrap: "wrap",
        marginBottom: 12,
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      {/* --- Liens à gauche --- */}
      <div
        style={{
          display: "flex",
          gap: 8,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        {item("/", "🏠 Accueil")}

        {/* Planification accessible aux encadrants et chefs */}
        {can("ADMIN", "OFFICIER", "CHEF_EQUIPE", "ADJ_CHEF_EQUIPE") &&
          item("/planning", "🗓️ Planification")}

        {/* Pages gestion internes */}
        {can("ADMIN", "OFFICIER") && (
          <>
            {item("/personnels", "🧑‍🚒 Gestion du personnel")}
            {item("/equipes", "🧩 Gestion équipes")}
            {item("/competences", "🧠 Compétences")}
            {item("/piquets", "🚒 Piquets")}
            {item("/calendrier-equipe", "📅 Calendrier d'équipe")}
          </>
        )}

        {can("ADMIN") && item("/admin/settings", "⚙️ Paramètres")} 

        {/* 🔹 Nouvelle page OPE : Saisie des gardes */}
        {can("ADMIN","OFFICIER","OPE") && item("/saisies-gardes", "📝 Saisies gardes")}
        {can("ADMIN","OFFICIER","OPE") && item("/vision-gardes", "👁️ Vision gardes")}
      </div>

      {/* --- Zone droite : utilisateur + logout --- */}
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        {user && (
          <span
            style={{
              color: "#eaf1ff",
              background: "#121a2f",
              borderRadius: 12,
              padding: "6px 10px",
              fontSize: 13,
              lineHeight: 1,
              whiteSpace: "nowrap",
            }}
            title={user.roles?.join(", ")}
          >
            {user.full_name || user.email}
          </span>
        )}
        <button
          onClick={logout}
          style={{
            background: "#b91c1c",
            color: "white",
            border: "none",
            borderRadius: 10,
            padding: "8px 12px",
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          Déconnexion
        </button>
      </div>
    </nav>
  );
}
