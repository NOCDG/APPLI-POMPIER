import React, { useEffect, useState } from "react";
import { listMyRealGardes, type MyRealGarde } from "../api";

export default function Home() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [gardes, setGardes] = useState<MyRealGarde[]>([]);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError("");
      try {
        // Une seule requête : le backend rapproche déjà la feuille et Agatt.
        setGardes(await listMyRealGardes(20));
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
            const isNight = g.slot === "NUIT";
            const remplace = g.etat === "remplace";
            const ajout = g.etat === "ajout";

            return (
              <div
                key={`${g.garde_id}-${g.etat}`}
                className={`home-card${remplace ? " home-card-remplace" : ""}`}
                style={{ position: "relative" }}
              >
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
                {g.equipe?.code && (
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
                    title={g.equipe.libelle || ""}
                  >
                    EQ {String(g.equipe.code).toUpperCase()}
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
                    className={g.piquet ? "chip" : "chip chip-none"}
                    title={
                      g.piquet
                        ? g.piquet.libelle || ""
                        : "Piquet non renseigné dans l'export Agatt"
                    }
                  >
                    {g.piquet
                      ? `👷 ${g.piquet.code || g.piquet.libelle || `Piquet #${g.piquet.id}`}`
                      : "👷 piquet à confirmer"}
                  </span>
                </div>

                {/* État vis-à-vis d'Agatt */}
                {(remplace || ajout || g.source === "feuille") && (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {remplace && (
                      <span
                        className="chip chip-remplace"
                        title="Vous n'apparaissez plus sur cette garde dans Agatt : le remplacement est enregistré."
                      >
                        ✕ Remplacé
                      </span>
                    )}
                    {ajout && (
                      <span
                        className="chip chip-ajout"
                        title="Vous prenez cette garde dans Agatt sans être sur la feuille : vous remplacez quelqu'un."
                      >
                        ↻ Remplacement
                      </span>
                    )}
                    {g.source === "feuille" && (
                      <span
                        className="chip chip-attente"
                        title="Garde pas encore saisie dans Agatt par l'opérateur : elle peut encore évoluer."
                      >
                        ⏳ Non saisie dans Agatt
                      </span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
