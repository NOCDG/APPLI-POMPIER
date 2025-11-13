// frontend/src/api/axios.ts
import axios from "axios";

const raw = import.meta.env.VITE_API_BASE_URL as string | undefined;
if (!raw) {
  console.error("VITE_API_BASE_URL non défini au build.");
  throw new Error("VITE_API_BASE_URL missing");
}

const api = axios.create({
  baseURL: raw.replace(/\/+$/, ""), // supprime le / final si présent
  // withCredentials: true, // active si tu utilises des cookies côté API
});

// (optionnel) JWT en header si stocké côté front
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
