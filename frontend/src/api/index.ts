import api from "./axios";

/**
 * Récupère les infos de l’utilisateur connecté
 * (dépend du token JWT envoyé automatiquement dans les headers)
 */
export async function getMe() {
  const response = await api.get("/users/me");
  return response.data;
}

/**
 * Liste les personnels (optionnellement filtrés par équipe)
 */
export async function listPersonnels(equipe_id?: number) {
  const response = await api.get("/personnels", {
    params: equipe_id ? { equipe_id } : {},
  });
  return response.data;
}

/**
 * Génère toutes les gardes du mois (backend : /gardes/generate_month_all)
 */
export async function generateMonth(year: number, month: number) {
  const response = await api.post("/gardes/generate_month_all", { year, month });
  return response.data;
}

/**
 * Liste les gardes d’un mois (et équipe si besoin)
 */
export async function listGardes(year: number, month: number, equipe_id?: number) {
  const response = await api.get("/gardes", {
    params: { year, month, equipe_id },
  });
  return response.data;
}
