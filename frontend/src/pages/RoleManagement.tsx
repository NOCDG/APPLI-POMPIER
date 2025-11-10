// src/pages/RoleManagement.tsx
import { useEffect, useState } from "react";
import api from "../api/axios";
import { useAuth } from "../auth/AuthContext";

type U = { id:number; email:string; equipe_id:number|null; roles:string[] };
const ALL_ROLES = ["ADMIN","OFFICIER","OPE","CHEF_EQUIPE","ADJ_CHEF_EQUIPE","AGENT"];

export default function RoleManagement(){
  const [users,setUsers]=useState<U[]>([]);
  const { user } = useAuth();

  useEffect(()=>{ api.get("/roles/list-users").then(r=>setUsers(r.data)); },[]);

  const toggle = async (u:U, role:string) => {
    if (role==="AGENT") return;
    const has = u.roles.includes(role);
    if (has) await api.post("/roles/revoke", { user_id:u.id, role });
    else await api.post("/roles/assign", { user_id:u.id, role });
    const fresh = await api.get("/roles/list-users"); setUsers(fresh.data);
  };

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold mb-4">Gestion des rôles</h1>
      <table className="min-w-full border">
        <thead><tr><th className="p-2 border">Email</th>{ALL_ROLES.map(r=><th key={r} className="p-2 border">{r}</th>)}</tr></thead>
        <tbody>
          {users.map(u=>(
            <tr key={u.id}>
              <td className="border p-2">{u.email}</td>
              {ALL_ROLES.map(r=>(
                <td key={r} className="border p-2 text-center">
                  {r==="AGENT"
                    ? (u.roles.includes(r) || true) ? "✓" : ""
                    : <input type="checkbox" checked={u.roles.includes(r)} onChange={()=>toggle(u,r)} />
                  }
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
