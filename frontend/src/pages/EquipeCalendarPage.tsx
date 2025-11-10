import React, { useEffect, useMemo, useState } from 'react'
import {
  listEquipes,
  listGardesAllMonth,
  assignTeamToSlot,
  generateMonthAll,
  listGardes, // ✅ on récupère TOUTES les gardes du mois (avec ou sans équipe)
} from '../api'
import './equipe-calendar.css'

type Equipe = { id:number; code:string; libelle:string; couleur?:string }
type Garde = {
  id:number
  date:string
  slot:'JOUR'|'NUIT'
  equipe_id:number | null
  is_holiday:boolean
  is_weekend:boolean
}

export default function EquipeCalendarPage() {
  const now = new Date()

  // Période affichée
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)

  // Données
  const [equipes, setEquipes] = useState<Equipe[]>([])
  const [gardesByKey, setGardesByKey] = useState<Record<string, Garde>>({}) // key: `${date}|${slot}`

  // Génération toutes équipes
  const [busyGenAll, setBusyGenAll] = useState(false)
  const [loading, setLoading] = useState(false)

  // Charge les équipes au montage (pour la liste de sélection)
  useEffect(() => {
    (async () => {
      try {
        const eqs = await listEquipes()
        setEquipes(eqs)
      } catch (e:any) {
        alert(e?.message || "Impossible de charger les équipes")
      }
    })()
  }, [])

  // Charge les gardes du mois pour **toutes** les équipes (y compris sans équipe)
  async function loadMonth() {
    setLoading(true)
    try {
      const all: Garde[] = await listGardesAllMonth(year, month) // ✅ un seul appel, pas de filtre d’équipe
      const map: Record<string, Garde> = {}
      for (const g of all) {
        map[`${g.date}|${g.slot}`] = g
      }
      setGardesByKey(map)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadMonth() }, [year, month])

  // Groupage: uniquement les jours qui ont AU MOINS un slot créé
  const groupedByDate = useMemo(() => {
    const acc = new Map<string, { date: string; slots: Array<'JOUR'|'NUIT'>; flags: {we:boolean; jf:boolean} }>()
    for (const key of Object.keys(gardesByKey)) {
      const [date, slot] = key.split('|') as [string, 'JOUR'|'NUIT']
      const g = gardesByKey[key]
      if (!acc.has(date)) {
        acc.set(date, { date, slots: [], flags: { we: false, jf: false } })
      }
      const item = acc.get(date)!
      if (!item.slots.includes(slot)) item.slots.push(slot)
      item.flags.we ||= !!g.is_weekend
      item.flags.jf ||= !!g.is_holiday
    }
    // tri par date croissante
    return Array.from(acc.values()).sort((a,b)=> a.date.localeCompare(b.date))
  }, [gardesByKey])

  function formatDate(iso: string) {
    const d = new Date(iso + 'T00:00:00')
    return d.toLocaleDateString(undefined, {
      weekday: 'short',
      day: '2-digit',
      month: 'short',
    })
  }

  function currentEquipeId(dateIso: string, slot: 'JOUR'|'NUIT'): number | '' {
    const g = gardesByKey[`${dateIso}|${slot}`]
    return g?.equipe_id ?? ''
  }

  async function onChangeEquipe(dateIso: string, slot: 'JOUR'|'NUIT', equipe_id_str: string) {
    if (!equipe_id_str) return
    const equipe_id = Number(equipe_id_str)
    try {
      const g = await assignTeamToSlot({ date: dateIso, slot, equipe_id })
      // MAJ locale
      setGardesByKey(prev => ({
        ...prev,
        [`${dateIso}|${slot}`]: {
          id: g?.id ?? prev[`${dateIso}|${slot}`]?.id ?? Math.random(),
          date: dateIso,
          slot,
          equipe_id,
          is_holiday: g?.is_holiday ?? prev[`${dateIso}|${slot}`]?.is_holiday ?? false,
          is_weekend: g?.is_weekend ?? prev[`${dateIso}|${slot}`]?.is_weekend ?? false,
        }
      }))
    } catch (e:any) {
      alert(e?.message || 'Affectation équipe impossible')
    }
  }

  async function onGenerateMonthForAllTeams() {
    try {
      setBusyGenAll(true)
      await generateMonthAll(year, month)
      await loadMonth()
    } catch (e:any) {
      alert(e?.message || 'Génération impossible (toutes équipes)')
    } finally {
      setBusyGenAll(false)
    }
  }

  return (
    <div className="ec-container">
      <h2 className="ec-title">📅 Calendrier des équipes de garde</h2>
      <p className="ec-subtitle">
        1) Créer toutes les gardes du mois pour <b>toutes</b> les équipes (NUIT en semaine, JOUR+NUIT les WE/JF).<br />
        2) Choisir l’équipe <b>active</b> pour chaque slot existant.
      </p>

      <div className="ec-toolbar">
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

        <button className="ec-btn" onClick={loadMonth}>🔄 Recharger</button>

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="ec-btn" onClick={onGenerateMonthForAllTeams} disabled={busyGenAll}>
            {busyGenAll ? 'Création…' : '⚙️ Créer pour TOUTES les équipes'}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="ec-subtitle">Chargement…</div>
      ) : groupedByDate.length === 0 ? (
        <div className="ec-subtitle">Aucun slot créé pour ce mois. Lance “Créer pour TOUTES les équipes”.</div>
      ) : (
        <div className="ec-grid">
          {groupedByDate.map(({ date, slots, flags }) => (
            <div key={date} className="ec-day">
              <div className="ec-day-head">
                <div className="ec-date">{formatDate(date)}</div>
                {flags.jf ? <span className="ec-chip">JF</span> : flags.we ? <span className="ec-chip">WE</span> : null}
              </div>

              {slots.map(slot => (
                <div key={slot} className="ec-row">
                  <div className="ec-slot">{slot}</div>
                  <select
                    className="ec-select"
                    value={currentEquipeId(date, slot)}
                    onChange={e => onChangeEquipe(date, slot, e.target.value)}
                  >
                    <option value="">—</option>
                    {equipes.map(eq => (
                      <option key={eq.id} value={eq.id}>{eq.code} — {eq.libelle}</option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
