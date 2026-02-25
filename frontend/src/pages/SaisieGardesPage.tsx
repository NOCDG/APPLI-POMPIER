import React, { useEffect, useMemo, useState } from "react";
import { useAuth } from "../auth/AuthContext";
import {
  listEquipes,
  listPiquets,
  listGardes,
  listAffectations,
  listPersonnels,
  patchAffectationOpeChecked, // ✅ nouveau nom (export réel dans api.ts)
  bulkOpeCheckForGarde,
  type Garde,
  type Equipe,
  type Piquet,
  type Affectation,
  type Personnel,
} from "../api";
import "./saisie-gardes.css";

type AffectationWithOpe = Affectation & {
  ope_checked?: boolean;
  ope_checked_at?: string | null;
};

export default function SaisieGardesPage() {
  const { hasAnyRole } = useAuth();
  const allowed = hasAnyRole("OPE");

  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const [equipes, setEquipes] = useState<Equipe[]>([]);
  const [piquets, setPiquets] = useState<Piquet[]>([]);
  const [gardes, setGardes] = useState<Garde[]>([]);
  const [affByGarde, setAffByGarde] = useState<Record<number, AffectationWithOpe[]>>({});
  const [personnels, setPersonnels] = useState<Personnel[]>([]);
  const [loading, setLoading] = useState(true);
  const [equipeFilter, setEquipeFilter] = useState<number | ''>('');

  // UI pending (évite double clic pendant requêtes)
  const [pendingAffIds, setPendingAffIds] = useState<Record<number, boolean>>({});
  const [pendingGardeIds, setPendingGardeIds] = useState<Record<number, boolean>>({});

  // charge bases
  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const [eqs, pqs, pers] = await Promise.all([
          listEquipes(),
          listPiquets(),
          listPersonnels(),
        ]);
        setEquipes(eqs);
        setPiquets(pqs);
        setPersonnels(pers);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function loadMonth() {
    setLoading(true);
    try {
      const gs = await listGardes({ year, month });
      setGardes(gs);

      const map: Record<number, AffectationWithOpe[]> = {};
      await Promise.all(
        gs.map(async (g) => {
          map[g.id] = (await listAffectations(g.id)) as any;
        })
      );
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
    return [...equipes].sort((a, b) => (a.code || "").localeCompare(b.code || ""));
  }, [equipes]);

  // map id_equipe -> couleur
  const equipeColorMap = useMemo(() => {
    const m: Record<number, string> = {};
    equipes.forEach((eq) => {
      // @ts-ignore
      const c = (eq as any).couleur ?? (eq as any).color;
      if (typeof c === "string" && c.trim()) m[eq.id] = c.trim();
    });
    return m;
  }, [equipes]);

  const eqColor = (eqId: number) => equipeColorMap[eqId] || "#607d8b";

  const persona = (id: number) => {
    const p = personnels.find((x) => x.id === id);
    return p ? `${p.nom} ${p.prenom}`.trim() : `#${id}`;
  };

  const isAstreinte = (piquet: Piquet | undefined) => {
    if (!piquet) return false;
    // @ts-ignore
    if (typeof (piquet as any).is_astreinte === "boolean" && (piquet as any).is_astreinte)
      return true;
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

  // ---- CHECKBOXES helpers (source de vérité = affByGarde[*].ope_checked) ----
  const isAffChecked = (a: AffectationWithOpe) => Boolean((a as any).ope_checked);

  const isAllChecked = (gardeId: number) => {
    const affs = affByGarde[gardeId] || [];
    if (affs.length === 0) return false;
    return affs.every((a) => isAffChecked(a));
  };

  const setAffLocal = (gardeId: number, affectationId: number, checked: boolean) => {
    setAffByGarde((prev) => {
      const list = prev[gardeId] || [];
      const next = list.map((a) =>
        a.id === affectationId ? ({ ...a, ope_checked: checked } as any) : a
      );
      return { ...prev, [gardeId]: next };
    });
  };

  const setAllLocal = (gardeId: number, checked: boolean) => {
    setAffByGarde((prev) => {
      const list = prev[gardeId] || [];
      const next = list.map((a) => ({ ...a, ope_checked: checked } as any));
      return { ...prev, [gardeId]: next };
    });
  };

  async function toggleAff(gardeId: number, aff: AffectationWithOpe, checked: boolean) {
    if (pendingAffIds[aff.id]) return;

    // UI optimiste
    setAffLocal(gardeId, aff.id, checked);
    setPendingAffIds((p) => ({ ...p, [aff.id]: true }));

    try {
      await patchAffectationOpeChecked(aff.id, { ope_checked: checked });
    } catch (e) {
      // rollback
      setAffLocal(gardeId, aff.id, !checked);
      alert("Impossible d'enregistrer la validation (serveur).");
    } finally {
      setPendingAffIds((p) => {
        const copy = { ...p };
        delete copy[aff.id];
        return copy;
      });
    }
  }

  async function toggleAllForGarde(gardeId: number, checked: boolean) {
    if (pendingGardeIds[gardeId]) return;

    // UI optimiste
    setAllLocal(gardeId, checked);
    setPendingGardeIds((p) => ({ ...p, [gardeId]: true }));

    try {
      await bulkOpeCheckForGarde(gardeId, { checked });

      // resync depuis le serveur (source de vérité)
      const updated = (await listAffectations(gardeId)) as any as AffectationWithOpe[];
      setAffByGarde((prev) => ({ ...prev, [gardeId]: updated }));
    } catch (e) {
      // rollback
      setAllLocal(gardeId, !checked);
      alert("Impossible d'enregistrer la validation globale (serveur).");
    } finally {
      setPendingGardeIds((p) => {
        const copy = { ...p };
        delete copy[gardeId];
        return copy;
      });
    }
  }

  // groupe par date, puis gJour/gNuit (avec filtre équipe)
  const gardesByDate: Array<[string, { jour: Garde | null; nuit: Garde | null }]> = useMemo(() => {
    const filtered = equipeFilter
      ? gardes.filter(g => g.equipe_id === Number(equipeFilter))
      : gardes;
    const map = new Map<string, { jour: Garde | null; nuit: Garde | null }>();
    for (const g of filtered) {
      const entry = map.get(g.date) || { jour: null, nuit: null };
      if (g.slot === "JOUR") entry.jour = g;
      else if (g.slot === "NUIT") entry.nuit = g;
      map.set(g.date, entry);
    }
    return Array.from(map.entries()).sort((a, b) => a[0].localeCompare(b[0]));
  }, [gardes, equipeFilter]);

  // rend un bloc (JOUR/NUIT) avec 3 sections : Gardes / Astreinte / Pro 24h
  function renderSlotBlock(label: "JOUR" | "NUIT", garde: Garde | null) {

    // Un agent est "pro sur cette garde" si statut PRO pur,
    // ou DOUBLE avec statut_service = "pro" sur cette affectation
    const isProOnGarde = (pers: Personnel, a: AffectationWithOpe) =>
      pers.statut === "pro" ||
      (pers.statut === "double" && a.statut_service === "pro");

    // Catégoriser toutes les affectations de cette garde en 3 groupes
    type Row = { aff: AffectationWithOpe; label: string; eqId: number };
    const gardeRows:    Row[] = [];
    const astreinteRows: Row[] = [];
    const pro24Rows:    Row[] = [];

    if (garde) {
      for (const a of affByGarde[garde.id] || []) {
        const pers = personnels.find((x) => x.id === a.personnel_id);
        if (!pers) continue;
        const row: Row = { aff: a, label: persona(pers.id), eqId: pers.equipe_id ?? 0 };
        if (isProOnGarde(pers, a)) {
          pro24Rows.push(row);
        } else if (isAstreinte(pqById.get(a.piquet_id))) {
          astreinteRows.push(row);
        } else {
          gardeRows.push(row);
        }
      }
    }

    // Rendu d'une liste d'agents dans une carte
    const renderCard = (key: React.Key, label: string, border: string, eqRows: Row[]) => (
      <div
        className="sg-eq-row sg-team-card"
        key={key}
        style={{ borderColor: border, backgroundColor: `${border}14` }}
      >
        <div className="sg-eq-label">{label}</div>
        <div className="sg-eq-names">
          <ul className="sg-list">
            {eqRows.sort((a, b) => a.label.localeCompare(b.label)).map((r) => (
              <li key={r.aff.id} className="sg-person-row">
                <span className="sg-person-name">{r.label}</span>
                {garde ? (
                  <input
                    className="sg-person-check"
                    type="checkbox"
                    checked={isAffChecked(r.aff)}
                    disabled={!!pendingAffIds[r.aff.id] || !!pendingGardeIds[garde.id]}
                    onChange={(e) => toggleAff(garde.id, r.aff, e.target.checked)}
                    title="Valider cet agent"
                  />
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
    );

    // Rendu groupé par équipe — les agents sans équipe (eqId=0) vont dans une carte "SPP"
    const renderEquipeCards = (rows: Row[]) => {
      if (rows.length === 0) return null;
      const knownEqIds = new Set(orderedEquipes.map(e => e.id));
      const orphans = rows.filter(r => !knownEqIds.has(r.eqId));
      return (
        <div className="sg-eq-table">
          {orderedEquipes.map((eq) => {
            const eqRows = rows.filter((r) => r.eqId === eq.id);
            if (eqRows.length === 0) return null;
            return renderCard(eq.id, eq.code, eqColor(eq.id), eqRows);
          })}
          {orphans.length > 0 && renderCard("orphans", "SPP", "#607d8b", orphans)}
        </div>
      );
    };

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
              <label className="sg-validated-checkbox" title="Cocher quand la saisie est terminée">
                <input
                  type="checkbox"
                  checked={isAllChecked(garde.id)}
                  disabled={!!pendingGardeIds[garde.id]}
                  onChange={(e) => toggleAllForGarde(garde.id, e.target.checked)}
                />
                <span>Saisie terminée</span>
              </label>
            </>
          ) : (
            <span className="sg-muted">— Aucune garde —</span>
          )}
        </div>

        <div className="sg-subtitle">🚒 Gardes</div>
        {renderEquipeCards(gardeRows)}

        <div className="sg-subtitle" style={{ marginTop: 10 }}>🏠 Astreinte</div>
        {renderEquipeCards(astreinteRows)}

        {pro24Rows.length > 0 && (
          <>
            <div className="sg-subtitle sg-subtitle-pro" style={{ marginTop: 10 }}>
              👨‍🚒 Pro 24h
            </div>
            {renderEquipeCards(pro24Rows)}
          </>
        )}
      </div>
    );
  }

  if (!allowed) {
    return (
      <div className="sg-container">
        <h2 className="sg-title">🔒 Accès restreint</h2>
        <p>
          Cette page est réservée au rôle <b>OPE</b>.
        </p>
      </div>
    );
  }

  return (
    <div className="sg-container">
      <h2 className="sg-title">🧾 Saisie gardes</h2>

      <div className="sg-toolbar">
        <select
          value={equipeFilter}
          onChange={(e) => setEquipeFilter(e.target.value ? Number(e.target.value) : '')}
        >
          <option value="">Toutes les équipes</option>
          {[...equipes].sort((a, b) => (a.code || '').localeCompare(b.code || '')).map((eq) => (
            <option key={eq.id} value={eq.id}>
              {eq.code}{eq.libelle ? ` — ${eq.libelle}` : ''}
            </option>
          ))}
        </select>
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
        <button className="sg-btn" onClick={loadMonth}>
          🔄 Recharger
        </button>
      </div>

      {loading && <div className="sg-muted">Chargement…</div>}

      {!loading && (
        <>
          {gardesByDate.length === 0 ? (
            <div className="sg-empty">Aucune garde pour ce mois.</div>
          ) : (
            <div className="sg-grid">
              {gardesByDate.map(([iso, pair]) => (
                <div className="sg-day" key={iso}>
                  <div className="sg-day-head">{formatDate(iso)}</div>
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
