import React, { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  listEquipes,
  listPiquets,
  listGardes,
  listAffectations,
  listPersonnels,
  type Garde, type Equipe, type Piquet, type Affectation, type Personnel
} from "../api";
import "./saisie-gardes.css";

export default function SaisieGardesPage() {
  const { hasAnyRole } = useAuth();
  const allowed = hasAnyRole("OPE"); // 🔒 réservé OPE

  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const [equipes, setEquipes] = useState<Equipe[]>([]);
  const [piquets, setPiquets] = useState<Piquet[]>([]);
  const [gardes, setGardes] = useState<Garde[]>([]);
  const [affByGarde, setAffByGarde] = useState<Record<number, Affectation[]>>({});
  const [personnels, setPersonnels] = useState<Personnel[]>([]);
  const [loading, setLoading] = useState(true);

  // charge bases
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [eqs, pqs, pers] = await Promise.all([listEquipes(), listPiquets(), listPersonnels()]);
        setEquipes(eqs);
        setPiquets(pqs);
        setPersonnels(pers);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // charge le mois (⚠️ on ne filtre plus : on prend tout)
  async function loadMonth() {
    setLoading(true);
    try {
      const gs = await listGardes({ year, month }); // ← toutes les gardes
      setGardes(gs);

      const map: Record<number, Affectation[]> = {};
      await Promise.all(gs.map(async (g) => {
        map[g.id] = await listAffectations(g.id);
      }));
      setAffByGarde(map);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadMonth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [year, month]);

  // utilitaires
  const eqById = useMemo(() => {
    const m = new Map<number, Equipe>();
    for (const e of equipes) m.set(e.id, e);
    return m;
  }, [equipes]);

  const pqById = useMemo(() => {
    const m = new Map<number, Piquet>();
    for (const p of piquets) m.set(p.id, p);
    return m;
  }, [piquets]);

  const orderedEquipes = useMemo(() => {
    // ordre A, B, C, D … (tri par code)
    return [...equipes].sort((a, b) => (a.code || "").localeCompare(b.code || ""));
  }, [equipes]);

  const persona = (id: number) => {
    const p = personnels.find((x) => x.id === id);
    return p ? `${p.nom} ${p.prenom}`.trim() : `#${id}`;
  };

  const isAstreinte = (piquet: Piquet | undefined) => {
    if (!piquet) return false;
    // 1) champ bool si présent
    // @ts-ignore
    if (typeof (piquet as any).is_astreinte === "boolean" && (piquet as any).is_astreinte) return true;
    // 2) fallback sur code/libellé commençant par "astreinte"
    const s = `${piquet.code || ""} ${piquet.libelle || ""}`.trim().toLowerCase();
    return s.startsWith("astreinte");
  };

  function formatDate(iso: string) {
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString(undefined, {
      weekday: "long",
      day: "2-digit",
      month: "long",
    });
  }

  // groupe par date, puis gJour/gNuit
  const gardesByDate: Array<[string, { jour: Garde | null; nuit: Garde | null }]> = useMemo(() => {
    const map = new Map<string, { jour: Garde | null; nuit: Garde | null }>();
    for (const g of gardes) {
      const entry = map.get(g.date) || { jour: null, nuit: null };
      if (g.slot === "JOUR") entry.jour = g;
      else if (g.slot === "NUIT") entry.nuit = g;
      map.set(g.date, entry);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [gardes]);

  // rend un bloc (JOUR/NUIT) avec 2 sections : Piquets / Astreinte, par équipe
  function renderSlotBlock(label: "JOUR" | "NUIT", garde: Garde | null) {
    const validated = garde ? Boolean((garde as any).validated) : false;
    const validatedAt = garde && (garde as any).validated_at
      ? new Date((garde as any).validated_at).toLocaleString()
      : null;

    // helper pour générer lignes d’une section selon filtre astreinte ou non
    const sectionRows = (wantAstreinte: boolean) => (
      <div className="sg-eq-table">
        {orderedEquipes.map((eq) => {
          const names: string[] = [];
          if (garde && validated) { // ⬅️ on ne remplit les noms que si la garde est validée
            const affs = affByGarde[garde.id] || [];
            for (const a of affs) {
              const pers = personnels.find((x) => x.id === a.personnel_id);
              if (!pers || pers.equipe_id !== eq.id) continue;
              const pqt = pqById.get(a.piquet_id);
              if (isAstreinte(pqt) !== wantAstreinte) continue;
              names.push(persona(pers.id));
            }
          }
          return (
            <div className="sg-eq-row" key={`${eq.id}-${wantAstreinte ? "ast" : "pqt"}`}>
              <div className="sg-eq-label">{eq.code}</div>
              <div className="sg-eq-names">
                {names.length ? (
                  <ul className="sg-list">
                    {names.sort((a, b) => a.localeCompare(b)).map((n) => (
                      <li key={n}>{n}</li>
                    ))}
                  </ul>
                ) : (
                  <span className="sg-empty-small">—</span>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );

    return (
      <div className="sg-slot-block">
        <div className="sg-slot-head">
          <span className="sg-slot">{label}</span>
          {garde ? (
            <>
              <span className={`sg-chip ${garde.is_holiday ? "jf" : garde.is_weekend ? "we" : ""}`}>
                {garde.is_holiday ? "JF" : garde.is_weekend ? "WE" : "SEM"}
              </span>
              <span className="sg-equipe-assigned">
                {garde.equipe_id ? (eqById.get(garde.equipe_id)?.code || `EQ#${garde.equipe_id}`) : "—"}
              </span>
              {validated ? (
                <span className="sg-badge-ok" title={validatedAt ? `Validée le ${validatedAt}` : "Validée"}>
                  ✅ Validée
                </span>
              ) : (
                <span className="sg-badge-bad" title="Non validée">❌ Non validée</span>
              )}
            </>
          ) : (
            <span className="sg-muted">— Aucune garde —</span>
          )}
        </div>

        {/* Section PIQUETS (hors astreinte) */}
        <div className="sg-subtitle">🚒 Gardes</div>
        {sectionRows(false)}

        {/* Section ASTREINTE */}
        <div className="sg-subtitle" style={{ marginTop: 10 }}>🏠 Astreinte</div>
        {sectionRows(true)}
      </div>
    );
  }

  // ====== RENDU ======
  if (!allowed) {
    return (
      <div className="sg-container">
        <h2 className="sg-title">🔒 Accès restreint</h2>
        <p>Cette page est réservée au rôle <b>OPE</b>.</p>
      </div>
    );
  }

  return (
    <div className="sg-container">
      <h2 className="sg-title">🧾 Saisie gardes</h2>

      {/* Barre de sélection */}
      <div className="sg-toolbar">
        <select value={month} onChange={(e) => setMonth(Number(e.target.value))}>
          {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
            <option key={m} value={m}>
              {new Date(2000, m - 1, 1).toLocaleDateString(undefined, { month: "long" })}
            </option>
          ))}
        </select>
        <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
          {Array.from({ length: 6 }, (_, i) => now.getFullYear() - 2 + i).map((y) => (
            <option key={y} value={y}>
              {y}
            </option>
          ))}
        </select>
        <button className="sg-btn" onClick={loadMonth}>🔄 Recharger</button>
      </div>

      {loading && <div className="sg-muted">Chargement…</div>}

      {/* Liste par jour */}
      {!loading && (
        <>
          {gardesByDate.length === 0 ? (
            <div className="sg-empty">Aucune garde pour ce mois.</div>
          ) : (
            <div className="sg-grid">
              {gardesByDate.map(([iso, pair]) => (
                <div className="sg-day" key={iso}>
                  <div className="sg-day-head">{formatDate(iso)}</div>

                  {/* n’affiche que les gardes existantes (NUIT semaine, JOUR+NUIT WE/JF) */}
                  {pair.jour && renderSlotBlock("JOUR", pair.jour)}
                  {pair.nuit && renderSlotBlock("NUIT", pair.nuit)}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
