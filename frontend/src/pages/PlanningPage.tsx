import React, { useEffect, useMemo, useState } from 'react'
import {
  listEquipes, listPiquets, listGardes, generateMonth,
  listAffectations, createAffectation, deleteAffectation,
  suggestPersonnels, listPersonnels, validateMonth, unvalidateMonth
} from '../api'
import { useAuth } from '../auth/AuthContext'
import './planning.css'

type Slot = 'JOUR' | 'NUIT'

type Garde = {
  id: number
  date: string
  slot: Slot
  is_weekend: boolean
  is_holiday: boolean
  equipe_id: number | null
  validated?: boolean
  validated_at?: string | null
}

type Piquet = {
  id: number
  nom: string
  description?: string | null
  code?: string
  libelle?: string
  is_astreinte?: boolean
}

type Equipe = {
  id: number
  nom: string
  couleur?: string | null
  code?: string
  libelle?: string
}

type Affectation = {
  id: number
  garde_id: number
  piquet_id: number
  personnel_id: number
  created_at?: string
  statut_service?: 'pro' | 'volontaire' | null
}

type Personnel = {
  id: number
  nom: string
  prenom: string
  equipe_id?: number | null
  statut?: string | null       // 🆕 pour gérer le double statut
}

type StatutService = 'pro' | 'volontaire'

export default function PlanningPage() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)

  const { user, hasAnyRole } = useAuth()
  const isChef = !!user?.roles?.some(r => r === 'CHEF_EQUIPE' || r === 'ADJ_CHEF_EQUIPE')
  const myEquipeId = user?.equipe_id ?? null

  // si chef: force l’équipe sur son équipe
  const [equipeId, setEquipeId] = useState<number | ''>(isChef && myEquipeId ? myEquipeId : '')
  useEffect(() => {
    if (isChef && myEquipeId) setEquipeId(myEquipeId)
  }, [isChef, myEquipeId])

  const [equipes, setEquipes] = useState<Equipe[]>([])
  const [piquets, setPiquets] = useState<Piquet[]>([])
  const [gardes, setGardes] = useState<Garde[]>([])
  const [affByGarde, setAffByGarde] = useState<Record<number, Affectation[]>>({})
  const [allPersonnels, setAllPersonnels] = useState<Personnel[]>([])

  // choix du statut pour un double
  const [statutChoice, setStatutChoice] = useState<{
    perso: Personnel
    gardeId: number
    piquetId: number
  } | null>(null)

  // ---- droits / verrouillage ----
  const [isMonthValidated, setIsMonthValidated] = useState(false)
  const canAdminOff = hasAnyRole('ADMIN', 'OFFICIER')
  const canModify = !isMonthValidated || canAdminOff
  const showActions = canModify
  const canValidate = isChef || canAdminOff

  // --- helpers noms ---
  function formatShortName(nom?: string, prenom?: string) {
    const n = (nom ?? '').trim().toUpperCase()
    const p = (prenom ?? '').trim()
    const initiale = p ? `${p[0].toUpperCase()}.` : ''
    return `${n} ${initiale}`.trim()
  }
  function personaShort(p: Personnel) {
    return formatShortName(p.nom, p.prenom)
  }

  // filtre équipe
  const filteredGardes = useMemo(() => {
    if (!equipeId) return gardes
    const eid = Number(equipeId)
    return gardes.filter(g => g.equipe_id === eid)
  }, [gardes, equipeId])

  // tri gardes
  const gardesSorted = useMemo(() => {
    const order = (s: Slot) => (s === 'JOUR' ? 0 : 1)
    const copy = [...filteredGardes]
    copy.sort((a, b) => {
      const ta = new Date(a.date).getTime()
      const tb = new Date(b.date).getTime()
      if (ta !== tb) return ta - tb
      return order(a.slot) - order(b.slot)
    })
    return copy
  }, [filteredGardes])

  // panneau “ajouter”
  const [panel, setPanel] = useState<{ garde: Garde; piquet: Piquet } | null>(null)
  const [search, setSearch] = useState('')
  const [suggests, setSuggests] = useState<Personnel[]>([])
  const [loadingSuggests, setLoadingSuggests] = useState(false)

  // ---- LOAD BASE ----
  useEffect(() => {
    ; (async () => {
      const [eqs, pqs, persons] = await Promise.all([listEquipes(), listPiquets(), listPersonnels()])
      setEquipes(eqs)
      setPiquets(pqs)
      setAllPersonnels(persons as any)
    })()
  }, [])

  async function loadMonth() {
    const equipeFilter =
      isChef ? (myEquipeId ?? undefined)
        : (equipeId !== '' ? Number(equipeId) : undefined)

    const gs: Garde[] = await listGardes({ year, month, equipe_id: equipeFilter as any })
    setGardes(gs)

    const map: Record<number, Affectation[]> = {}
    await Promise.all(gs.map(async g => {
      map[g.id] = await listAffectations(g.id) as any
    }))
    setAffByGarde(map)
  }

  useEffect(() => { loadMonth() }, [year, month, equipeId, isChef, myEquipeId])

  useEffect(() => {
    const all = filteredGardes
    const validated = all.length > 0 && all.every(g => (g as any).validated === true)
    setIsMonthValidated(validated)
  }, [filteredGardes])

  async function onGenerate() {
    if (!hasAnyRole('ADMIN', 'OFFICIER', 'OPE')) return
    await generateMonth(year, month)
    await loadMonth()
  }

  // ---- UTILS ----
  function formatDate(iso: string) {
    const d = new Date(iso + 'T00:00:00')
    return d.toLocaleDateString(undefined, { weekday: 'short', day: '2-digit', month: 'short' })
  }

  function affFor(gardeId: number, piquetId: number) {
    const list = affByGarde[gardeId] || []
    return list.find(a => a.piquet_id === piquetId)
  }

  async function openPanel(g: Garde, p: Piquet) {
    if (!canModify) return
    setPanel({ garde: g, piquet: p })
    setSearch('')
    setSuggests([])
    try {
      setLoadingSuggests(true)
      const res = await suggestPersonnels(g.id, p.id)
      setSuggests(res as any)
    } finally {
      setLoadingSuggests(false)
    }
  }

  // 🆕 choisit le statut pour un double via 2 boutons
  async function confirmStatutChoice(choice: StatutService) {
    if (!statutChoice) return
    try {
      await createAffectation({
        garde_id: statutChoice.gardeId,
        piquet_id: statutChoice.piquetId,
        personnel_id: statutChoice.perso.id,
        statut_service: choice,
      } as any)

      const updated = await listAffectations(statutChoice.gardeId)
      setAffByGarde(prev => ({ ...prev, [statutChoice.gardeId]: updated as any }))
      setPanel(null)
    } catch (e: any) {
      alert(e?.message || 'Affectation impossible')
    } finally {
      setStatutChoice(null)
    }
  }

  function cancelStatutChoice() {
    setStatutChoice(null)
  }

  // 🆕 ajout avec gestion du double statut → ouvre la popin de choix si besoin
  async function add(personnel_id: number) {
    if (!panel) return
    try {
      const perso = allPersonnels.find(p => p.id === personnel_id) || null

      let statut_service: StatutService | undefined

      if (perso && perso.statut) {
        const st = (perso.statut || '').toLowerCase()
        if (st === 'pro' || st === 'volontaire') {
          // simple : un seul statut
          statut_service = st as StatutService
        } else if (st === 'double') {
          // on ouvre la popin de choix, et on s'arrête là
          setStatutChoice({
            perso,
            gardeId: panel.garde.id,
            piquetId: panel.piquet.id,
          })
          return
        }
      }

      await createAffectation({
        garde_id: panel.garde.id,
        piquet_id: panel.piquet.id,
        personnel_id,
        statut_service,
      } as any)

      const updated = await listAffectations(panel.garde.id)
      setAffByGarde(prev => ({ ...prev, [panel.garde.id]: updated as any }))
      setPanel(null)
    } catch (e: any) {
      alert(e?.message || 'Affectation impossible')
    }
  }

  async function remove(aff: Affectation) {
    if (!canModify) return
    if (!confirm('Supprimer cette affectation ?')) return
    await deleteAffectation(aff.id)
    const updated = await listAffectations(aff.garde_id)
    setAffByGarde(prev => ({ ...prev, [aff.garde_id]: updated as any }))
  }

  const filteredManual = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return []
    return allPersonnels
      .filter(p => (`${p.nom} ${p.prenom}`).toLowerCase().includes(q))
      .slice(0, 20)
  }, [search, allPersonnels])

  const piquetCode = (p: Piquet) => p.code ?? p.nom
  const piquetLib = (p: Piquet) => p.libelle ?? p.description ?? ''

  // ---- handlers validation / dévalidation ----
  async function handleToggleValidation(nextChecked: boolean) {
    const equipeFilter =
      isChef ? (myEquipeId ?? undefined)
        : (equipeId !== '' ? Number(equipeId) : undefined)

    if (nextChecked) {
      if (!canValidate) {
        alert("Vous n'avez pas les droits pour valider.")
        return
      }
      if (!isChef && !equipeFilter) {
        alert("Veuillez choisir une équipe avant de valider.")
        return
      }
      const ok = window.confirm(
        "Confirmer la validation de la feuille de garde du mois ?\n\n" +
        "Après validation, elle ne sera plus modifiable par les chefs d'équipe.\n" +
        "Seuls ADMIN et OFFICIER pourront modifier ou dévalider."
      )
      if (!ok) return
      await validateMonth({ year, month, equipe_id: equipeFilter as any })
      await loadMonth()
      return
    } else {
      if (!canAdminOff) {
        alert("Dévalidation réservée à ADMIN et OFFICIER.")
        return
      }
      const ok = window.confirm(
        "Voulez-vous vraiment dévalider la feuille de garde du mois ?\n\n" +
        "Elle redevient modifiable par les chefs d'équipe."
      )
      if (!ok) return
      await unvalidateMonth({ year, month, equipe_id: equipeFilter as any })
      await loadMonth()
      return
    }
  }

  // --- rendu d'une “carte garde” ---
  const renderCard = (g: Garde | null) => {
    if (!g) return null
    const cardLocked = !canModify
    const badge = g.is_holiday ? 'JF' : (g.is_weekend ? 'WE' : null)

    return (
      <div key={g.id} className="pl-day" style={{ minWidth: 260 }}>
        <div className="pl-day-head">
          <div className="pl-date">{formatDate(g.date)} — <b>{g.slot}</b></div>
          {badge && <span className="pl-chip">{badge}</span>}
        </div>

        <div className={`pl-garde ${g.slot === 'JOUR' ? 'day' : 'night'} ${cardLocked ? 'locked' : ''}`}>
          <div className="pl-garde-head">
            <b>{g.slot}</b>
            {g.validated && (
              <span
                className="pl-chip small"
                title={
                  g.validated_at
                    ? `Validée le ${new Date(g.validated_at).toLocaleString()}`
                    : 'Validée'
                }
              >
                validée
              </span>
            )}
          </div>

          <div className="pl-rows">
            {piquets.map(p => {
              const aff = affFor(g.id, p.id)
              const perso = aff ? (allPersonnels.find(x => x.id === aff.personnel_id) || null) : null
              const personaTxt = perso ? personaShort(perso) : ''
              return (
                <div key={p.id} className="pl-row">
                  <div className="pl-piquet">{piquetCode(p)}</div>
                  <div
                    className="pl-assignee"
                    title={piquetLib(p)}
                    style={{
                      width: 120,
                      minWidth: 110,
                      maxWidth: 140,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {aff ? (
                      <span className="pl-pill">{personaTxt}</span>
                    ) : (
                      <span className="pl-empty-small">—</span>
                    )}
                  </div>
                  <div className="pl-actions">
                    {showActions ? (
                      !aff ? (
                        <button
                          className="pl-icon-btn add"
                          title="Ajouter"
                          onClick={() => openPanel(g, p)}
                        >
                          ➕
                        </button>
                      ) : (
                        <button
                          className="pl-icon-btn remove"
                          title="Supprimer"
                          onClick={() => remove(aff!)}
                        >
                          ❌
                        </button>
                      )
                    ) : null}
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
    <div className="pl-container">
      <h2 className="pl-title">🗓️ Planification des gardes</h2>

      {/* Barre de sélection */}
      <div className="pl-toolbar">
        <select
          value={isChef ? (myEquipeId ?? '') : equipeId}
          onChange={e => setEquipeId(e.target.value ? Number(e.target.value) : '')}
          disabled={isChef}
          title={isChef ? 'Accès limité à votre équipe' : 'Choisir une équipe'}
        >
          <option value="">{isChef ? 'Mon équipe' : 'Équipe…'}</option>
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

        <button className="pl-btn" onClick={loadMonth}>🔄 Recharger</button>

        {/* Validation / dévalidation */}
        <label
          className="pl-switch"
          title={
            isMonthValidated
              ? (canAdminOff ? 'Dévalider (ADMIN/OFFICIER)' : 'Feuille validée – lecture seule pour les chefs')
              : (canValidate ? 'Valider la feuille (mois)' : 'Vous ne pouvez pas valider')
          }
        >
          <input
            type="checkbox"
            checked={isMonthValidated}
            onChange={async (e) => {
              try {
                await handleToggleValidation(e.target.checked)
              } catch (err: any) {
                alert(err?.message || "Erreur lors de la mise à jour de la validation")
                await loadMonth()
              }
            }}
          />
          <span>{isMonthValidated ? 'Feuille validée' : 'Valider la feuille'}</span>
        </label>

        {isMonthValidated && (
          <span
            className="pl-badge-ok"
            title={canAdminOff ? 'Modifiable/Dévalidable (ADMIN/OFFICIER)' : 'Verrouillée pour les chefs'}
          >
            ✅ Validée
          </span>
        )}
      </div>

      {/* Ruban horizontal du mois */}
      <div className="pl-month-strip pl-fullbleed">
        {gardesSorted.length === 0 && (
          <div className="pl-empty">Aucune garde pour ce mois/équipe.</div>
        )}
        {gardesSorted.map(g => renderCard(g))}
      </div>

      {/* Panneau "Ajouter" */}
      {panel && (
        <div className="pl-panel">
          <div className="pl-panel-card">
            <div className="pl-panel-head">
              <div>
                <div className="pl-panel-title">
                  Ajouter — {piquetCode(panel.piquet)} · {formatDate(panel.garde.date)} · {panel.garde.slot}
                </div>
                <div className="pl-panel-sub">{piquetLib(panel.piquet)}</div>
              </div>
              <button className="pl-x" onClick={() => setPanel(null)}>✖</button>
            </div>

            <div className="pl-panel-block">
              <div className="pl-subtitle">⭐ Suggestions</div>
              {loadingSuggests ? (
                <div className="pl-muted">Chargement…</div>
              ) : (suggests.length === 0 ? (
                <div className="pl-muted">Aucune suggestion</div>
              ) : (
                <div className="pl-suggests">
                  {suggests.map((s: any) => (
                    <button key={s.id} className="pl-suggest" onClick={() => add(s.id)}>
                      {formatShortName(s.nom, s.prenom)} {s.equipe_id ? <span className="pl-chip">EQ {s.equipe_id}</span> : null}
                    </button>
                  ))}
                </div>
              ))}
            </div>

            <div className="pl-panel-block">
              <div className="pl-subtitle">🔎 Recherche</div>
              <input
                className="pl-input"
                placeholder="Nom / Prénom…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
              <div className="pl-results">
                {filteredManual.map(p => (
                  <button key={p.id} className="pl-result" onClick={() => add(p.id)}>
                    {personaShort(p)} {p.equipe_id ? <span className="pl-chip">EQ {p.equipe_id}</span> : null}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Popin choix statut pour double statut */}
      {statutChoice && (
        <div className="pl-panel pl-panel-overlay">
          <div className="pl-panel-card">
            <div className="pl-panel-head">
              <div>
                <div className="pl-panel-title">
                  Choisir le statut de service
                </div>
                <div className="pl-panel-sub">
                  {statutChoice.perso.prenom} {statutChoice.perso.nom} est en double statut.
                </div>
              </div>
              <button className="pl-x" onClick={cancelStatutChoice}>✖</button>
            </div>

            <div className="pl-panel-block" style={{ display: 'flex', gap: 12, justifyContent: 'center' }}>
              <button
                className="pl-btn"
                onClick={() => confirmStatutChoice('pro')}
              >
                👨‍🚒 Professionnel
              </button>
              <button
                className="pl-btn"
                onClick={() => confirmStatutChoice('volontaire')}
              >
                🤝 Volontaire
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Actions de génération */}
      {hasAnyRole('ADMIN', 'OFFICIER', 'OPE') && (
        <div style={{ marginTop: 12 }}>
          <button className="pl-btn" onClick={onGenerate}>⚙️ Générer le mois</button>
        </div>
      )}
    </div>
  )
}
