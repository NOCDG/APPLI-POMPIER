// src/auth/AuthContext.tsx
import { createContext, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import api from "../api/axios";
import { getMe } from "../api"; // Assure-toi que ../api exporte bien getMe()
import { AxiosError } from "axios";

type User = {
  id: number;
  email: string;
  full_name?: string;
  equipe_id?: number | null;
  roles: string[];
};

type AuthCtx = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasAnyRole: (...roles: string[]) => boolean;
};

const Ctx = createContext<AuthCtx>(null!);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const raw = localStorage.getItem("me");
    return raw ? JSON.parse(raw) : null;
  });
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  // Bootstrap session au montage
  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) { setLoading(false); return; }
    api.get("/users/me")
      .then(r => {
        setUser(r.data);
        localStorage.setItem("me", JSON.stringify(r.data));
      })
      .catch(err => {
        console.error("Bootstrap /users/me failed:", err);
        localStorage.removeItem("token");
        localStorage.removeItem("me");
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    try {
      // 1) Auth
      const r = await api.post("/auth/login", { email, password });
      const token = r?.data?.access_token as string | undefined;

      if (!token) {
        console.error("Login OK mais pas de access_token dans la réponse:", r?.data);
        throw new Error("Réponse invalide du serveur (pas de token).");
      }

      // 2) Stocker le token (l’interceptor l’ajoutera tout seul ensuite)
      localStorage.setItem("token", token);

      // 3) Qui suis-je ?
      const me = await getMe();
      if (!me || !me.id) {
        console.error("getMe() invalide:", me);
        throw new Error("Impossible de récupérer le profil.");
      }
      localStorage.setItem("me", JSON.stringify(me));
      setUser(me);

      // 4) Vers l’accueil
      navigate("/");
    } catch (e: any) {
      // Nettoyage en cas d’échec
      localStorage.removeItem("token");
      localStorage.removeItem("me");
      setUser(null);

      // Log détaillé en console dev
      console.error("Login flow failed:", e);

      // Propage une erreur explicite au composant Login
      const ax = e as AxiosError<any>;
      const data = ax.response?.data;
      const detail = typeof data?.detail === "string"
        ? data.detail
        : Array.isArray(data?.detail)
          ? data.detail.map((x: any) => x?.msg ?? JSON.stringify(x)).join(" | ")
          : ax.message || "Erreur inconnue";

      throw new Error(detail);
    }
  };

  const hasAnyRole = (...need: string[]) => {
    const roles = user?.roles ?? [];
    if (!need || need.length === 0) return true;
    return need.some(r => roles.includes(r));
  };

  const logout = () => {
    localStorage.removeItem("token");
    localStorage.removeItem("me");
    setUser(null);
    navigate("/login");
  };

  return (
    <Ctx.Provider value={{ user, loading, login, logout, hasAnyRole }}>
      {children}
    </Ctx.Provider>
  );
}
