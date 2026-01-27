import React, { useEffect, useMemo, useState } from 'react'
import {
  listEquipes, listPiquets, listGardes,
  listAffectations, listPersonnels,
  type Garde, type Piquet, type Equipe, type Affectation, type Personnel
} from '../api'
import './Visiongarde.css'

export default function VisionGardesPage() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)

  // ✅ filtre équipe (mémoire)
  const [equipeId, setEquipeId] = useState<number | ''>('')

  const [equipes, setEquipes] = useState<Equipe[]>([])
  const [piquets, setPiquets] = useState<Piquet[]>([])
  const [gardes, setGardes] = useState<Garde[]>([])
  const [affByGarde, setAffByGarde] = useState<Record<number, Affectation[]>>({})
  const [allPersonnels, setAllPersonnels] = useState<Personnel[]>([])
  const [loading, setLoading] = useState(true)

  // ---- LOAD BASE ----
  useEffect(() => {
    (async () => {
      setLoading(true)
      try {
        const [eqs, pqs, persons] = await Promise.all([listEquipes(), listPiquets(), listPersonnels()])
        setEquipes(eqs)
        setPiquets(pqs)
        setAllPersonnels(persons)
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  async function loadMonth() {
    setLoading(true)
    try {
      // ← NE PAS FILTRER en API : on garde toutes les gardes en mémoire
      const gs: Garde[] = await listGardes({ year, month })
      setGardes(gs)

      const map: Record<number, Affectation[]> = {}
      await Promise.all(gs.map(async g => { map[g.id] = await listAffectations(g.id) }))
      setAffByGarde(map)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadMonth() }, [year, month])

  // ✅ Filtre en mémoire
  const filteredGardes = useMemo(() => {
    if (equipeId === '') return gardes
    const eid = Number(equipeId)

    // supporte garde.equipe_id typé ou pas (selon ton type importé)
    return gardes.filter(g => (g as any).equipe_id === eid)
  }, [gardes, equipeId])

  const daysGrouped = useMemo(() => {
    const by = new Map<string, Garde[]>()
    for (const g of filteredGardes) {
      const key = g.date
      if (!by.has(key)) by.set(key, [])
      by.get(key)!.push(g)
    }
    const arr = Array.from(by.entries()).sort((a, b) => a[0].localeCompare(b[0]))
    // tri JOUR avant NUIT
    for (const [, list] of arr) { list.sort((a, b) => a.slot.localeCompare(b.slot)) }
    return arr
  }, [filteredGardes])

  const formatDate = (iso: string) => {
    const d = new Date(iso + 'T00:00:00')
    return d.toLocaleDateString(undefined, { weekday: 'short', day: '2-digit', month: 'short' })
  }
  const persona = (p: Personnel) => `${p.nom} ${p.prenom}`.trim()
  const piquetCode = (p: Piquet) => p.code
  const piquetLib = (p: Piquet) => p.libelle ?? ''
  const affFor = (gardeId: number, piquetId: number) =>
    (affByGarde[gardeId] || []).find(a => a.piquet_id === piquetId)

  return (
    <div className="pl-container">
      <h2 className="pl-title">🗓️ PIQUETS </h2>

      {/* Barre de sélection */}
      <div className="pl-toolbar">
        {/* ✅ Filtre équipe */}
        <select
          value={equipeId}
          onChange={e => setEquipeId(e.target.value ? Number(e.target.value) : '')}
          title="Filtrer par équipe"
        >
          <option value="">Toutes les équipes</option>
          {equipes.map(eq => (
            <option key={eq.id} value={eq.id}>
              {(eq.code ?? eq.nom)} {eq.libelle ? `— ${eq.libelle}` : ''}
            </option>
          ))}
        </select>

        <select value={month} onChange={e => setMonth(Number(e.target.value))}>
          {Array.from({ length: 12 }, (_, i) => i + 1).map(m =>
            <option key={m} value={m}>
              {new Date(2000, m - 1, 1).toLocaleDateString(undefined, { month: 'long' })}
            </option>
          )}
        </select>

        <select value={year} onChange={e => setYear(Number(e.target.value))}>
          {Array.from({ length: 5 }, (_, i) => now.getFullYear() - 1 + i).map(y =>
            <option key={y} value={y}>{y}</option>
          )}
        </select>

        <button className="pl-btn" onClick={loadMonth} disabled={loading}>
          🔄 Recharger
        </button>
      </div>

      {loading && <div className="pl-muted">Chargement…</div>}

      {/* Grille des jours */}
      {!loading && (
        <div className="pl-grid">
          {daysGrouped.length === 0 && (
            <div className="pl-empty">Aucune garde pour ce mois{equipeId ? '/équipe.' : '.'}</div>
          )}

          {daysGrouped.map(([iso, gs]) => {
            const gJour = gs.find(g => g.slot === 'JOUR') || null
            const gNuit = gs.find(g => g.slot === 'NUIT') || null
            const badge = (gs[0] as any)?.is_holiday ? 'JF' : ((gs[0] as any)?.is_weekend ? 'WE' : null)

            const renderCard = (g: Garde | null) => {
              if (!g) return null
              const validated = Boolean((g as any).validated)
              const validatedAt = (g as any).validated_at
                ? new Date((g as any).validated_at).toLocaleString()
                : null

              return (
                <div key={g.id} className="pl-day">
                  <div className="pl-day-head">
                    <div className="pl-date">{formatDate(g.date)} — <b>{g.slot}</b></div>
                    {badge && <span className="pl-chip">{badge}</span>}
                    {validated ? (
                      <span className="pl-badge-ok" title={validatedAt ? `Validée le ${validatedAt}` : 'Validée'}>
                        ✅ Validée
                      </span>
                    ) : (
                      <span className="pl-badge-bad" title="Non validée">❌ Non validée</span>
                    )}
                  </div>

                  <div className={`pl-garde ${g.slot === 'JOUR' ? 'day' : 'night'}`}>
                    <div className="pl-garde-head">
                      <b>{g.slot}</b>
                    </div>

                    <div className="pl-rows">
                      {piquets.map(p => {
                        const aff = affFor(g.id, p.id)
                        const person = aff
                          ? allPersonnels.find(x => x.id === aff.personnel_id)
                          : undefined
                        return (
                          <div key={p.id} className="pl-row">
                            <div className="pl-piquet" title={piquetLib(p)}>{piquetCode(p)}</div>
                            <div className="pl-assignee">
                              {validated && person ? (
                                <span className="pl-pill">{persona(person)}</span>
                              ) : (
                                <span className="pl-empty-small">—</span>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </div>
                  </div>
                </div>
              )
            }

            return (
              <React.Fragment key={iso}>
                {/* n’affiche que les gardes existantes (NUIT semaine, JOUR+NUIT WE/JF) */}
                {gJour && renderCard(gJour)}
                {gNuit && renderCard(gNuit)}
              </React.Fragment>
            )
          })}
        </div>
      )}
    </div>
  )
}
