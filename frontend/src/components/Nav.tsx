import React from "react"
import { NavLink, Link } from "react-router-dom"
import { useAuth } from "../auth/AuthContext"
import { useTheme } from "../ThemeContext"

export default function Nav() {
  const { user, logout, hasAnyRole } = useAuth()
  const { theme, toggle } = useTheme()

  const can = (...roles: string[]) => hasAnyRole(...roles)

  const navLink = (to: string, label: string, end = false) => (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => "nav-link" + (isActive ? " active" : "")}
    >
      {label}
    </NavLink>
  )

  return (
    <header className="nav-header">
      <div className="nav-inner">

        {/* Ligne 1 : marque + contrôles utilisateur */}
        <div className="nav-top">
          <Link to="/" className="nav-brand">
            <span className="nav-badge">FG</span>
            <span className="nav-brand-name">Feuille de Garde</span>
          </Link>

          <div className="nav-right">
            <button
              className="nav-theme-btn"
              onClick={toggle}
              title={theme === "dark" ? "Mode clair" : "Mode sombre"}
              aria-label="Basculer le thème"
            >
              {theme === "dark" ? "☀" : "☽"}
            </button>

            {user && (
              <span className="nav-user" title={user.roles?.join(", ")}>
                {user.full_name || user.email}
              </span>
            )}

            <button className="nav-logout" onClick={logout}>
              Déconnexion
            </button>
          </div>
        </div>

        {/* Ligne 2 : liens de navigation */}
        <nav className="nav-links">
          {navLink("/", "Accueil", true)}

          {can("ADMIN", "OFFICIER", "CHEF_EQUIPE", "ADJ_CHEF_EQUIPE") &&
            navLink("/planning", "Planification")}

          {can("ADMIN", "OFFICIER") && (
            <>
              {navLink("/personnels", "Personnel")}
              {navLink("/equipes", "Équipes")}
              {navLink("/competences", "Compétences")}
              {navLink("/piquets", "Piquets")}
              {navLink("/calendrier-equipe", "Calendrier")}
            </>
          )}

          {can("ADMIN", "OFFICIER", "OPE") &&
            navLink("/saisies-gardes", "Saisies gardes")}

          {can("ADMIN", "OFFICIER", "OPE", "AGENT") &&
            navLink("/vision-gardes", "Gardes")}

          {can("ADMIN") &&
            navLink("/admin/settings", "⚙ Paramètres")}
        </nav>

      </div>
    </header>
  )
}
