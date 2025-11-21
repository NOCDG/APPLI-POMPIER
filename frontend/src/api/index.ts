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
  // En prod, on NE veut PAS de fallback silencieux vers localhost.
  // Ça permet de détecter immédiatement une mauvaise config CI/CD.
  // En dev, .env.development doit aussi la fournir.
  // eslint-disable-next-line no-console
  console.error("VITE_API_BASE_URL n'est pas défini au build !");
  throw new Error("VITE_API_BASE_URL is missing.");
}

const baseURL = raw.replace(/\/+$/, ""); // supprime trailing slash

const api = axios.create({
  baseURL,
  // withCredentials: true, // si tu utilises des cookies côté API
});

// (optionnel) Authorization: Bearer si tu stockes le token côté front
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
export async function healthCheck() {
  const res = await api.get("/health");
  return res.data;
}

export async function login(payload: { email: string; password: string }) {
  const res = await api.post("/auth/login", payload);
  return res.data; // { access_token, token_type, roles }
}

export async function getMe() {
  const res = await api.get("/users/me");
  return res.data;
}