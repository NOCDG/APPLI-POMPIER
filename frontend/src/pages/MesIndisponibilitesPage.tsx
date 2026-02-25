import React, { useEffect, useMemo, useState } from 'react'
import {
  listGardes, listIndisponibilites, createIndisponibilite, deleteIndisponibilite,
  type Indisponibilite,
} from '../api'
import { useAuth } from '../auth/AuthContext'
import './MesIndisponibilites.css'

type Garde = {
  id: number
  date: string
  slot: 'JOUR' | 'NUIT'
  is_weekend: boolean
  is_holiday: boolean
  equipe_id: number | null
}

export default function MesIndisponibilitesPage() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)

  const { user } = useAuth()
  const myId = user?.id ?? null
  const myEquipeId = user?.equipe_id ?? null

  const [gardes, setGardes] = useState<Garde[]>([])
  const [myIndispos, setMyIndispos] = useState<Indisponibilite[]>([])
  const [loading, setLoading] = useState(false)

  function formatDate(iso: string) {
    const d = new Date(iso + 'T00:00:00')
    return d.toLocaleDateString('fr-FR', { weekday: 'short', day: '2-digit', month: 'short' })
  }

  async function load() {
    if (!myEquipeId || !myId) return
    setLoading(true)
    try {
      const [gs, indis] = await Promise.all([
        listGardes({ year, month, equipe_id: myEquipeId }),
        listIndisponibilites(undefined, myId),
      ])
      const gardeIds = new Set((gs as Garde[]).map(g => g.id))
      setGardes(gs as Garde[])
      setMyIndispos(indis.filter(i => gardeIds.has(i.garde_id)))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [year, month, myEquipeId, myId])

  async function toggle(gardeId: number) {
    if (!myId) return
    const existing = myIndispos.find(i => i.garde_id === gardeId)
    try {
      if (existing) {
        await deleteIndisponibilite(existing.id)
        setMyIndispos(prev => prev.filter(i => i.id !== existing.id))
      } else {
        const created = await createIndisponibilite(gardeId, myId)
        setMyIndispos(prev => [...prev, created])
      }
    } catch (e: any) {
      alert(e?.response?.data?.detail || e?.message || 'Erreur')
    }
  }

  const gardesSorted = useMemo(() => {
    return [...gardes].sort((a, b) => {
      const ta = new Date(a.date).getTime()
      const tb = new Date(b.date).getTime()
      if (ta !== tb) return ta - tb
      return a.slot === 'JOUR' ? -1 : 1
    })
  }, [gardes])

  if (!myEquipeId) {
    return (
      <div className="mi-container">
        <h2 className="mi-title">Mes Indisponibilités</h2>
        <div className="mi-info warn">
          Votre compte n'est associé à aucune équipe. Contactez un administrateur.
        </div>
      </div>
    )
  }

  const indispoCount = myIndispos.length

  return (
    <div className="mi-container">
      <h2 className="mi-title">Mes Indisponibilités</h2>
      <p className="mi-subtitle">
        Signalez les gardes où vous êtes indisponible. Votre chef d'équipe en sera informé lors de la planification.
      </p>

      <div className="mi-toolbar">
        <select value={month} onChange={e => setMonth(Number(e.target.value))}>
          {Array.from({ length: 12 }, (_, i) => i + 1).map(m => (
            <option key={m} value={m}>
              {new Date(2000, m - 1, 1).toLocaleDateString('fr-FR', { month: 'long' })}
            </option>
          ))}
        </select>
        <select value={year} onChange={e => setYear(Number(e.target.value))}>
          {Array.from({ length: 3 }, (_, i) => now.getFullYear() - 1 + i).map(y => (
            <option key={y} value={y}>{y}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <div className="mi-empty">Chargement…</div>
      ) : gardesSorted.length === 0 ? (
        <div className="mi-empty">Aucune garde ce mois-ci pour votre équipe.</div>
      ) : (
        <>
          <div className="mi-summary">
            {indispoCount === 0
              ? 'Aucune indisponibilité déclarée ce mois-ci.'
              : `${indispoCount} indisponibilité${indispoCount > 1 ? 's' : ''} déclarée${indispoCount > 1 ? 's' : ''} ce mois-ci.`
            }
          </div>

          <div className="mi-grid">
            {gardesSorted.map(g => {
              const isIndispo = myIndispos.some(i => i.garde_id === g.id)
              return (
                <div
                  key={g.id}
                  className={`mi-card ${isIndispo ? 'indispo' : 'dispo'}`}
                  onClick={() => toggle(g.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={e => e.key === 'Enter' && toggle(g.id)}
                  title={isIndispo ? 'Cliquer pour se rendre disponible' : 'Cliquer pour se déclarer indisponible'}
                >
                  <div className="mi-card-top">
                    <span className={`mi-slot-icon ${g.slot === 'JOUR' ? 'jour' : 'nuit'}`}>
                      {g.slot === 'JOUR' ? '☀' : '🌙'}
                    </span>
                    {(g.is_holiday || g.is_weekend) && (
                      <span className="mi-chip">{g.is_holiday ? 'JF' : 'WE'}</span>
                    )}
                  </div>

                  <div className="mi-card-date">{formatDate(g.date)}</div>
                  <div className="mi-card-slot">{g.slot}</div>

                  <div className="mi-card-status">
                    {isIndispo
                      ? <span className="mi-status indispo">🚫 Indisponible</span>
                      : <span className="mi-status dispo">✓ Disponible</span>
                    }
                  </div>
                </div>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
