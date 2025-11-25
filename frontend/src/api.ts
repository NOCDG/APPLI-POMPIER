// src/api.ts
import axios, { AxiosError } from "axios";

/* ============================
   AXIOS + HELPERS
============================ */

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
});

export default api;

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export function apiErrorMessage(err: unknown): string {
  const e = err as AxiosError<any>;
  const data = e?.response?.data;
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg ?? JSON.stringify(x)).join(" | ");
  if (typeof data === "string") return data;
  return e.message || "Erreur réseau";
}

/* ============================
   TYPES LIGHT
============================ */
export type Role = "ADMIN" | "OFFICIER" | "OPE" | "CHEF_EQUIPE" | "ADJ_CHEF_EQUIPE" | "AGENT";
export type UserMe = { id: number; email: string; full_name?: string; equipe_id?: number|null; roles: Role[]; };

export type Statut = "pro" | "volontaire" | "double";

export type Personnel = {
  id: number;
  nom: string;
  prenom: string;
  grade: string;                     // 🆕 présent côté backend & front
  email: string;
  statut: Statut;                    // 🆕 plus un string libre
  equipe_id?: number | null;
};

export type PersonnelCreatePayload = {
  nom: string;
  prenom: string;
  grade: string;
  email: string;
  statut: Statut;
  equipe_id?: number | null;
  roles?: Role[];
};

export type PersonnelCreateResponse = {
  personnel: Personnel;
  temp_password: string;
};

export type Competence = { id: number; code?: string|null; nom: string; description?: string|null; };
export type Equipe = { id: number; code: string; libelle: string; couleur?: string|null };
export type Piquet = { id: number; code: string; libelle: string };

export type Garde = {
  id: number;
  date: string;
  slot: "JOUR"|"NUIT";
  is_weekend: boolean;
  is_holiday: boolean;
  equipe_id?: number|null;
  // NEW: pour le verrou
  validated?: boolean;
  validated_at?: string | null;
};

export type Affectation = {
  id: number;
  garde_id: number;
  piquet_id: number;
  personnel_id: number;
  statut_service?: "pro" | "volontaire" | null;  // 🆕 info renvoyée par le backend
};

export type SuggestionMini = { id: number; nom: string; prenom: string; equipe_id?: number|null; };

/* ============================
   AUTH
============================ */
export async function login(email: string, password: string): Promise<{ access_token: string; token_type: string; roles: Role[] }>{
  const r = await api.post("/auth/login", { email, password });
  const data = r.data || {};
  const token = data.access_token ?? data.token ?? data.jwt ?? null;
  if (!token) throw new Error("Réponse invalide du serveur (pas de token).");
  localStorage.setItem("token", token);
  return { access_token: token, token_type: "bearer", roles: data.roles ?? [] };
}

export function logout(){
  localStorage.removeItem("token");
  localStorage.removeItem("me");
}

export async function getMe(): Promise<UserMe>{
  const r = await api.get("/users/me");
  localStorage.setItem("me", JSON.stringify(r.data));
  return r.data;
}

export function getCachedMe(): UserMe | null {
  const raw = localStorage.getItem("me");
  return raw ? JSON.parse(raw) as UserMe : null;
}
export function setCachedMe(u: UserMe | null){
  if (!u) localStorage.removeItem("me");
  else localStorage.setItem("me", JSON.stringify(u));
}

/* ============================
   ROLES
============================ */
export async function listAllRoles(): Promise<Role[]> {
  try { const r = await api.get("/roles"); return r.data; }
  catch { return ["ADMIN","OFFICIER","OPE","CHEF_EQUIPE","ADJ_CHEF_EQUIPE","AGENT"]; }
}
export async function listPersonnelRoles(personnel_id: number): Promise<Role[]>{
  const r = await api.get(`/roles/${personnel_id}`); return r.data;
}
export async function assignRoleToPersonnel(personnel_id: number, role: Role){
  const r = await api.post("/roles/assign", { personnel_id, role }); return r.data;
}
export async function removeRoleFromPersonnel(personnel_id: number, role: Role){
  const r = await api.post("/roles/revoke", null, { params: { personnel_id, role } });
  return r.data;
}

/* ============================
   PERSONNELS
============================ */
export async function listPersonnels(equipe_id?: number): Promise<Personnel[]>{
  const r = await api.get("/personnels", { params: equipe_id ? { equipe_id } : {} }); return r.data;
}
export async function getPersonnel(id: number): Promise<Personnel>{
  const r = await api.get(`/personnels/${id}`); return r.data;
}

export async function createPersonnel(
  payload: PersonnelCreatePayload
): Promise<PersonnelCreateResponse> {
  const r = await api.post("/personnels", payload);
  return r.data as PersonnelCreateResponse;
}

export async function updatePersonnel(
  id: number,
  payload: Partial<Personnel>
): Promise<Personnel> {
  const r = await api.put(`/personnels/${id}`, payload);
  return r.data;
}

export async function deletePersonnel(id: number){
  const r = await api.delete(`/personnels/${id}`); return r.data;
}
export async function setPersonnelEquipe(personnel_id: number, equipe_id: number | null){
  const r = await api.put(`/personnels/${personnel_id}`, { equipe_id });
  return r.data;
}

export async function deletePersonnelCompetenceByLink(link_id: number){
  const r = await api.delete(`/personnels/competences/${link_id}`);
  return r.data;
}

/* --- compétences d’un personnel --- */
export async function addCompetenceToPersonnel(personnel_id: number, competence_id: number, date_obtention?: string, date_expiration?: string){
  const r = await api.post(`/personnels/${personnel_id}/competences`, { competence_id, date_obtention, date_expiration }); return r.data;
}
export async function deleteCompetenceFromPersonnel(personnel_id: number, competence_id: number){
  const r = await api.delete(`/personnels/${personnel_id}/competences/${competence_id}`); return r.data;
}
export async function listCompetencesOfPersonnel(personnel_id: number){
  const r = await api.get(`/personnels/${personnel_id}/competences`); return r.data;
}

/* ============================
   COMPETENCES
============================ */
export async function listCompetences(): Promise<Competence[]>{
  const r = await api.get("/competences"); return r.data;
}
export async function createCompetence(payload: { nom: string; description?: string; code?: string }): Promise<Competence>{
  const r = await api.post("/competences", payload); return r.data;
}
export async function updateCompetence(id: number, payload: Partial<Competence>): Promise<Competence>{
  const r = await api.put(`/competences/${id}`, payload); return r.data;
}
export async function deleteCompetence(id: number){
  const r = await api.delete(`/competences/${id}`); return r.data;
}

/* ============================
   EQUIPES
============================ */
export async function listEquipes(): Promise<Equipe[]>{
  const r = await api.get("/equipes"); return r.data;
}
export async function createEquipe(payload: { nom: string; couleur?: string|null }): Promise<Equipe>{
  const r = await api.post("/equipes", payload); return r.data;
}
export async function updateEquipe(id: number, payload: Partial<Equipe>): Promise<Equipe>{
  const r = await api.put(`/equipes/${id}`, payload); return r.data;
}
export async function deleteEquipe(id: number){
  const r = await api.delete(`/equipes/${id}`); return r.data;
}

/* ============================
   PIQUETS (+ compétences)
============================ */

// Créer un piquet { code, libelle, exigences?: number[] }
export async function createPiquet(payload: { code: string; libelle: string; exigences?: number[] }) {
  const r = await api.post('/piquets', payload);
  return r.data;
}

// Lister
export async function listPiquets() {
  const r = await api.get('/piquets');
  return r.data;
}

// Supprimer
export async function deletePiquet(piquet_id: number) {
  await api.delete(`/piquets/${piquet_id}`);
  return true;
}

// ➕ Ajouter une compétence requise à un piquet
export async function addCompetenceToPiquet(piquet_id: number, competence_id: number) {
  const r = await api.post(`/piquets/${piquet_id}/exigences`, { competence_id });
  return r.data;
}

// 🗑️ Retirer une compétence requise d’un piquet
export async function removeCompetenceFromPiquet(piquet_id: number, competence_id: number) {
  const r = await api.delete(`/piquets/${piquet_id}/exigences/${competence_id}`);
  return r.data;
}

// Réordonner
export async function reorderPiquets(ids: number[]) {
  const r = await api.put('/piquets/reorder', { piquet_ids: ids });
  return r.data;
}

/* ============================
   GARDES
============================ */
export async function listGardes(params: { year: number; month: number; equipe_id?: number | '' }) {
  const { year, month, equipe_id } = params;
  const q: any = { year, month };
  if (equipe_id !== undefined && equipe_id !== '') q.equipe_id = Number(equipe_id);
  const r = await api.get('/gardes', { params: q });
  return r.data as Garde[];
}

// Renvoie TOUTES les gardes du mois, avec ou sans équipe
export async function listGardesAllMonth(year: number, month: number) {
  const r = await api.get('/gardes/all', { params: { year, month } });
  return r.data as Garde[];
}

export async function generateMonthAll(
  yearOrObj: number | string | { year: number | string; month: number | string },
  monthMaybe?: number | string
) {
  let body: { year: number; month: number };
  if (typeof yearOrObj === 'object' && yearOrObj !== null) {
    body = { year: Number(yearOrObj.year), month: Number(yearOrObj.month) };
  } else {
    body = { year: Number(yearOrObj), month: Number(monthMaybe) };
  }
  const r = await api.post('/gardes/generate_month_all', body);
  return r.data;
}

export async function generateMonth(year: number, month: number){
  const r = await api.post("/gardes/generate_month", { year, month });
  return r.data;
}

// Assigner une équipe à un jour/slot
export async function assignTeam(payload: { date: string; slot: 'JOUR'|'NUIT'; equipe_id: number }) {
  const r = await api.put('/gardes/assign_team', payload);
  return r.data; // GardeRead
}

// Retirer l’équipe d’un jour/slot
export async function clearTeam(payload: { date: string; slot: 'JOUR'|'NUIT' }) {
  const r = await api.put('/gardes/clear_team', payload);
  return r.data; // GardeRead
}

// ✅ Valider le mois (chef pour son équipe; admin/off pour tout)
export async function validateMonth(payload: {year:number; month:number; equipe_id?:number}) {
  const params: any = { annee: payload.year, mois: payload.month };
  if (payload.equipe_id !== undefined) params.equipe_id = payload.equipe_id;
  const r = await api.post('/gardes/valider-mois', null, { params });
  return r.data;
}

// ✅ Dévalider le mois (admin/off uniquement)
export async function unvalidateMonth(payload: { year: number; month: number; equipe_id?: number }) {
  const params: any = { annee: payload.year, mois: payload.month };
  if (payload.equipe_id !== undefined) params.equipe_id = payload.equipe_id;
  const r = await api.post('/gardes/devalider-mois', null, { params });
  return r.data;
}

export type MyUpcoming = {
  affectation_id: number;
  garde_id: number;
  date: string;
  slot: "JOUR" | "NUIT";
  is_weekend: boolean;
  is_holiday: boolean;
  piquet: { id: number; code: string; libelle?: string | null };
  equipe?: { id: number; code: string; libelle?: string | null } | null;
};

// API
export async function listMyUpcomingAffectations(limit = 10, fromISO?: string): Promise<MyUpcoming[]> {
  const r = await api.get('/affectations/mine_upcoming', {
    params: { limit, start: fromISO },
  });
  return r.data as MyUpcoming[];
}

/* ============================
   AFFECTATIONS
============================ */
export async function listAffectations(garde_id?: number){
  const r = await api.get("/affectations", { params: garde_id ? { garde_id } : {} });
  return r.data as Affectation[];
}

export async function createAffectation(payload: {
  garde_id: number;
  piquet_id: number;
  personnel_id: number;
  statut_service?: "pro" | "volontaire";  // 🆕 optionnel
}) {
  const r = await api.post("/affectations", payload);
  return r.data as Affectation;
}

export async function deleteAffectation(id: number){
  const r = await api.delete(`/affectations/${id}`);
  return r.data;
}

/* ============================
   SUGGESTIONS
============================ */
export async function suggestPersonnels(garde_id: number, piquet_id: number): Promise<SuggestionMini[]>{
  const r = await api.get(`/gardes/${garde_id}/suggest-personnels`, { params: { piquet_id } });
  return r.data;
}

/* ============================
   ALIAS DE COMPATIBILITÉ
============================ */

// PiquetsPage.tsx
export async function addPiquetCompetence(piquet_id: number, competence_id: number){
  return addCompetenceToPiquet(piquet_id, competence_id);
}
export async function deletePiquetCompetence(piquet_id: number, competence_id: number){
  return removeCompetenceFromPiquet(piquet_id, competence_id);
}

// EquipeCalendarPage.tsx
export async function assignTeamToSlot(payload: { date: string; slot: "JOUR"|"NUIT"; equipe_id: number }) {
  return assignTeam(payload);
}
export async function clearTeamFromSlot(payload: { date: string; slot: "JOUR"|"NUIT" }) {
  return clearTeam(payload);
}

// PersonnelsPage.tsx
export async function deletePersonnelCompetence(personnel_id: number, competence_id: number){
  return deleteCompetenceFromPersonnel(personnel_id, competence_id);
}

// Aliases CRUD "get/save" utilisés dans certains projets
export async function getCompetences(){ return listCompetences(); }
export async function saveCompetence(payload: Partial<Competence> & { id?: number }){
  return payload.id ? updateCompetence(payload.id, payload) : createCompetence(payload as any);
}
export async function getEquipes(){ return listEquipes(); }
export async function saveEquipe(payload: Partial<Equipe> & { id?: number }){
  return payload.id ? updateEquipe(payload.id, payload) : createEquipe(payload as any);
}
export async function getPiquets(){ return listPiquets(); }
export async function savePiquet(payload: Partial<Piquet> & { id?: number }){
  // NOTE: tu avais un updatePiquet référencé dans d'autres projets.
  // S'il te faut un update côté piquet, ajoute une route backend et exporte-la ici.
  return payload.id ? Promise.reject(new Error("updatePiquet non implémenté")) : createPiquet(payload as any);
}
export async function getPersonnels(){ return listPersonnels(); }
export async function savePersonnel(payload: Partial<Personnel> & { id?: number }){
  return payload.id ? updatePersonnel(payload.id, payload) : createPersonnel(payload as any);
}


// ============================
// SETTINGS (admin)
// ============================

export type MailTemplates = {
  admin_validation_subject: string;
  admin_validation_html: string;   // HTML avec variables
  user_validation_subject: string;
  user_validation_html: string;    // HTML avec variables (inclut {{tableau_gardes}})
};

export type AppSettings = {
  POSTGRES_DB: string;
  POSTGRES_USER: string;
  POSTGRES_PASSWORD: string;
  POSTGRES_HOST?: string;
  POSTGRES_PORT?: number;
  CORS_ORIGINS: string[];
  BACKEND_PORT?: number;
  FRONTEND_PORT?: number;
  TZ: string;
  JWT_SECRET: string;
  MAIL_USERNAME: string;
  MAIL_PASSWORD: string;
  MAIL_FROM: string;
  MAIL_PORT: number;
  MAIL_SERVER: string;
  MAIL_FROM_NAME: string;
  MAIL_TLS: boolean;
  MAIL_SSL: boolean;
  VITE_API_URL?: string;
  MAIL_NOTIFY_TO: string;

  // templates
  mail_templates: MailTemplates;
};

export async function getAppSettings(): Promise<AppSettings> {
  const r = await api.get("/settings");
  return r.data as AppSettings;
}

export async function saveAppSettings(payload: AppSettings) {
  const r = await api.put("/settings", payload);
  return r.data;
}

export async function testEmail(to: string) {
  const r = await api.post("/settings/test-email", { to });
  return r.data;
}

// --- Mot de passe oublié / reset ---

export async function forgotPassword(email: string) {
  const r = await api.post("/auth/forgot-password", { email });
  return r.data;
}

export async function resetPassword(token: string, newPassword: string) {
  const r = await api.post("/auth/reset-password", {
    token,
    new_password: newPassword,
  });
  return r.data;
}