// src/pages/RoleManagement.tsx
import { useEffect, useState } from "react";
import api from "../api/axios";
import { useAuth } from "../auth/AuthContext";

type U = { id: number; email: string; equipe_id: number | null; roles: string[] };
const ALL_ROLES = ["ADMIN", "OFFICIER", "OPE", "CHEF_EQUIPE", "ADJ_CHEF_EQUIPE", "AGENT"];

export default function RoleManagement() {
  const [users, setUsers] = useState<U[]>([]);
  const { user } = useAuth();

  useEffect(() => {
    api.get("/roles/list-users").then((r) => setUsers(r.data));
  }, []);

  const toggle = async (u: U, role: string) => {
    if (role === "AGENT") return;
    const has = u.roles.includes(role);
    if (has) await api.post("/roles/revoke", { user_id: u.id, role });
    else await api.post("/roles/assign", { user_id: u.id, role });
    const fresh = await api.get("/roles/list-users");
    setUsers(fresh.data);
  };

  return (
    <div className="pg-container">
      <h2 className="pg-title">🎭 Gestion des rôles</h2>
      <p className="pg-subtitle">Attribue ou retire des rôles aux utilisateurs.</p>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Email</th>
              {ALL_ROLES.map((r) => (
                <th key={r} style={{ textAlign: "center" }}>{r}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.id}>
                <td style={{ fontWeight: 500 }}>{u.email}</td>
                {ALL_ROLES.map((r) => (
                  <td key={r} style={{ textAlign: "center" }}>
                    {r === "AGENT" ? (
                      <span style={{ color: "var(--text-muted)", fontSize: 12 }}>
                        {u.roles.includes(r) ? "✓" : "—"}
                      </span>
                    ) : (
                      <input
                        type="checkbox"
                        checked={u.roles.includes(r)}
                        onChange={() => toggle(u, r)}
                        style={{ cursor: "pointer", width: 16, height: 16 }}
                      />
                    )}
                  </td>
                ))}
              </tr>
            ))}
            {users.length === 0 && (
              <tr>
                <td colSpan={ALL_ROLES.length + 1} style={{ color: "var(--text-muted)", textAlign: "center", padding: "20px" }}>
                  Aucun utilisateur
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
