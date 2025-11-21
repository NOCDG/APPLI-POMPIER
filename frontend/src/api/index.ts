// frontend/src/api/axios.ts
import axios from "axios";

/**
 * On lit l'URL d'API uniquement via les variables d'env du build Vite.
 * - .env.development => dev
 * - .env.production  => prod (CI/CD)
 * On retire un éventuel slash final pour éviter les // dans les URLs.
 */
const raw = import.meta.env.VITE_API_BASE_URL as string | undefined;
if (!raw) {
  console.error("VITE_API_BASE_URL n'est pas défini au build !");
  throw new Error("VITE_API_BASE_URL is missing.");
}

export const api = axios.create({
  baseURL: raw.replace(/\/+$/, ""),
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;

// Ping /health (optionnel)
export async function getMe() {
  const res = await api.get("/users/me");
  return res.data;
}

export async function listEquipes() {
  const res = await api.get("/equipes");
  return res.data;
}