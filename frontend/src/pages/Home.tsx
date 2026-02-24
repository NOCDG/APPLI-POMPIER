import React, { useEffect, useMemo, useState } from "react";
import {
  getCachedMe, getMe,
  listAffectations, // on récupère MES affectations
  listGardes,      // on charge les gardes du mois courant + suivant (sans filtre équipe)
  listEquipes,     // pour afficher l'équipe de chaque garde
  getPiquets,      // pour afficher le code du piquet
  type Equipe as EqType,
} from "../api";

type Garde = {
  id: number;
  date: string;
  slot: "JOUR" | "NUIT";
  is_weekend: boolean;
  is_holiday: boolean;
  equipe_id?: number | null;
  validated?: boolean;
};

type Piquet = { id: number; code?: string; libelle?: string };
type Affectation = { id: number; garde_id: number; piquet_id: number; personnel_id: number };
type EquipeMini = { id: number; code?: string; libelle?: string; couleur?: string | null } & Partial<EqType>;

export default function Home() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [affectations, setAffectations] = useState<Affectation[]>([]);
  const [gardes, setGardes] = useState<Garde[]>([]);
  const [equipesMap, setEquipesMap] = useState<Record<number, EquipeMini>>({});
  const [piquetsMap, setPiquetsMap] = useState<Record<number, Piquet>>({});

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError("");
      try {
        // 1) Qui suis-je ?
        const me = getCachedMe() || (await getMe());

        // 2) Mes affectations (toutes)
        let myAffects: Affectation[] = [];
        try {
          const all = await listAffectations(); // ton API accepte sans params (sinon adapter en ?personnel_id=me.id)
          myAffects = (all || []).filter((a: Affectation) => a.personnel_id === me.id);
        } catch (e: any) {
          throw new Error(e?.message || "Impossible de récupérer vos affectations.");
        }
        setAffectations(myAffects);

        // 3) Les piquets (pour lire le code)
        const ps = await getPiquets();
        const pmap: Record<number, Piquet> = {};
        for (const p of ps) pmap[p.id] = p;
        setPiquetsMap(pmap);

        // 4) Les équipes (pour badge équipe sur la carte)
        const eqs = await listEquipes();
        const emap: Record<number, EquipeMini> = {};
        for (const e of eqs) emap[(e as any).id] = e as any;
        setEquipesMap(emap);

        // 5) Gardes du mois courant + suivant (sans filtre équipe) puis on garde celles où j’ai une affectation
        const now = new Date();
        const y1 = now.getFullYear();
        const m1 = now.getMonth() + 1;
        const next = new Date(y1, m1, 1);
        const y2 = next.getFullYear();
        const m2 = next.getMonth() + 1;

        const [g1, g2] = await Promise.all([
          listGardes({ year: y1, month: m1 }), // pas d’equipe_id
          listGardes({ year: y2, month: m2 }),
        ]);

        const gardeIdsMine = new Set(myAffects.map((a) => a.garde_id));
        const todayISO = new Date().toISOString().slice(0, 10);

        const merged = [...(g1 || []), ...(g2 || [])]
          .filter((g: Garde) => gardeIdsMine.has(g.id) && g.date >= todayISO && g.validated === true)
          .sort((a: Garde, b: Garde) =>
            a.date === b.date ? (a.slot > b.slot ? 1 : -1) : a.date.localeCompare(b.date),
          )
          .slice(0, 20);

        setGardes(merged);
      } catch (e: any) {
        setError(e?.message || "Impossible de charger vos prochaines gardes.");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  function formatDate(iso: string) {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString(undefined, {
      weekday: "long",
      day: "2-digit",
      month: "long",
    });
  }

  // retrouver le piquet lié à une garde où je suis affecté
  function piquetForGarde(garde_id: number): Piquet | null {
    const aff = affectations.find((a) => a.garde_id === garde_id);
    return aff ? piquetsMap[aff.piquet_id] || null : null;
  }

  // retrouver l’équipe d’une garde
  function equipeForGarde(g: Garde): EquipeMini | null {
    if (!g.equipe_id && g.equipe_id !== 0) return null;
    return equipesMap[g.equipe_id as number] || null;
    }

  return (
    <div>
      <h2 style={{ marginBottom: 16 }}>🗓️ Mes prochaines gardes</h2>

      {loading ? (
        <div className="home-skel-list">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="home-skel" />
          ))}
        </div>
      ) : error ? (
        <div className="home-alert">{error}</div>
      ) : gardes.length === 0 ? (
        <div className="home-empty" style={{ color: "var(--muted)" }}>
          Aucune affectation à venir.
        </div>
      ) : (
        <div className="home-list">
          {gardes.map((g) => {
            const piquet = piquetForGarde(g.id);
            const eq = equipeForGarde(g);
            const isNight = g.slot === "NUIT";
            return (
              <div key={g.id} className="home-card" style={{ position: "relative" }}>
                {/* Date + badges WE/JF */}
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
                  <div style={{ fontWeight: 700, textTransform: "capitalize" }}>
                    {formatDate(g.date)}{" "}
                    {g.is_holiday
                      ? <span className="chip chip-jf">JF</span>
                      : g.is_weekend
                      ? <span className="chip chip-we">WE</span>
                      : null}
                  </div>
                </div>

                {/* Badge équipe en haut-droite */}
                {eq?.code && (
                  <div
                    style={{
                      position: "absolute",
                      top: 10,
                      right: 10,
                      background: "var(--accent)",
                      color: "var(--on-accent)",
                      padding: "3px 10px",
                      borderRadius: 999,
                      fontSize: 12,
                      fontWeight: 800,
                      textTransform: "uppercase",
                      zIndex: 2,
                    }}
                    title={eq.libelle || ""}
                  >
                    EQ {String(eq.code).toUpperCase()}
                  </div>
                )}

                {/* Slot + Piquet */}
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <span
                    style={{
                      background: isNight ? "var(--accent)" : "var(--ok)",
                      color: "#fff",
                      borderRadius: 999,
                      padding: "4px 10px",
                      fontWeight: 700,
                      fontSize: 12,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                    }}
                  >
                    {isNight ? "🌙 Nuit" : "☀️ Jour"}
                  </span>

                  <span
                    className="chip"
                    title={piquet?.libelle || ""}
                  >
                    {piquet ? `👷 ${piquet.code || piquet.libelle || `Piquet #${piquet.id}`}` : "—"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
