import React, { useEffect, useMemo, useState } from 'react'
import {
  listEquipes, listPiquets, listGardes, generateMonth,
  listAffectations, createAffectation, deleteAffectation,
  suggestPersonnels, listPersonnels, validateMonth, unvalidateMonth,
  listIndisponibilites, createIndisponibilite, deleteIndisponibilite,
  listDisposAgatt,
  listProDeGarde,
  downloadPdfFeuille,
  type Indisponibilite,
  type DispoAgatt,
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
  statut?: string | null // gérer le double statut
}

type StatutService = 'pro' | 'volontaire'

export default function PlanningPage() {
  const now = new Date()
  const [year, setYear] = useState(now.getFullYear())
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [zoom, setZoom] = useState<number>(() => {
    const s = localStorage.getItem('pl-zoom')
    return s ? parseFloat(s) : 1.0
  })

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
  const [indisByGarde, setIndisByGarde] = useState<Record<number, Indisponibilite[]>>({})
  const [allPersonnels, setAllPersonnels] = useState<Personnel[]>([])

  // 🆕 map id_equipe -> couleur
  const equipeColorMap = useMemo(() => {
    const m: Record<number, string> = {}
    equipes.forEach(eq => {
      if (eq.couleur) m[eq.id] = eq.couleur
    })
    return m
  }, [equipes])

  // ✅ séparation GARDE / ASTREINTE
  const { piquetsGarde, piquetsAstreinte } = useMemo(() => {
    const garde: Piquet[] = []
    const astreinte: Piquet[] = []
    for (const p of piquets) {
      if (p.is_astreinte === true) astreinte.push(p)
      else garde.push(p)
    }
    return { piquetsGarde: garde, piquetsAstreinte: astreinte }
  }, [piquets])

  // choix du statut pour un double
  const [statutChoice, setStatutChoice] = useState<{
    perso: Personnel
    gardeId: number
    piquetId: number
  } | null>(null)

  const [pdfLoading, setPdfLoading] = useState(false)

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

  // filtre équipe (côté UI)
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
  const [searchResults, setSearchResults] = useState<Personnel[]>([])
  const [loadingSearch, setLoadingSearch] = useState(false)
  const [disposAgatt, setDisposAgatt] = useState<DispoAgatt[]>([])
  const [loadingDispos, setLoadingDispos] = useState(false)
  const [proDeGarde, setProDeGarde] = useState<DispoAgatt[]>([])
  const [loadingPro, setLoadingPro] = useState(false)

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
    const indiMap: Record<number, Indisponibilite[]> = {}
    await Promise.all(gs.map(async g => {
      map[g.id] = await listAffectations(g.id) as any
      indiMap[g.id] = await listIndisponibilites(g.id)
    }))
    setAffByGarde(map)
    setIndisByGarde(indiMap)
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
    setSearchResults([])
    setDisposAgatt([])
    setProDeGarde([])

    const isAstreinte = (p as any).is_astreinte === true

    setLoadingSuggests(true)
    setLoadingDispos(true)
    setLoadingPro(true)
    try {
      const [sugRes, disposRes, proRes] = await Promise.all([
        suggestPersonnels(g.id, p.id),
        listDisposAgatt(g.date, g.slot, isAstreinte, p.id),
        listProDeGarde(g.date),
      ])
      setSuggests(sugRes as any)
      setDisposAgatt(disposRes)
      setProDeGarde(proRes)
    } finally {
      setLoadingSuggests(false)
      setLoadingDispos(false)
      setLoadingPro(false)
    }
  }

  // choisit le statut pour un double via 2 boutons
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

  // ajout avec gestion du double statut → ouvre la popin de choix si besoin
  async function add(personnel_id: number) {
    if (!panel) return
    try {
      const perso = allPersonnels.find(p => p.id === personnel_id) || null

      let statut_service: StatutService | undefined

      if (perso && perso.statut) {
        const st = (perso.statut || '').toLowerCase()
        if (st === 'pro' || st === 'volontaire') {
          statut_service = st as StatutService
        } else if (st === 'double') {
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

  async function toggleIndispo(gardeId: number, personnelId: number) {
    if (!canModify) return
    const existing = (indisByGarde[gardeId] || []).find(i => i.personnel_id === personnelId)
    if (existing) {
      await deleteIndisponibilite(existing.id)
      setIndisByGarde(prev => ({
        ...prev,
        [gardeId]: (prev[gardeId] || []).filter(i => i.id !== existing.id),
      }))
    } else {
      const created = await createIndisponibilite(gardeId, personnelId)
      setIndisByGarde(prev => ({
        ...prev,
        [gardeId]: [...(prev[gardeId] || []), created],
      }))
    }
  }

  useEffect(() => {
    if (!search.trim() || !panel) {
      setSearchResults([])
      return
    }
    const timer = setTimeout(async () => {
      setLoadingSearch(true)
      try {
        const res = await suggestPersonnels(panel.garde.id, panel.piquet.id, search.trim(), false)
        setSearchResults(res as any)
      } catch {
        setSearchResults([])
      } finally {
        setLoadingSearch(false)
      }
    }, 300)
    return () => clearTimeout(timer)
  }, [search, panel])

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

  // ✅ équipe "effective" (celle réellement affichée)
  const effectiveEquipeId: number | null = useMemo(() => {
    if (isChef) return myEquipeId ?? null
    return equipeId !== '' ? Number(equipeId) : null
  }, [isChef, myEquipeId, equipeId])

  // ✅ personnels non affectés PAR GARDE (dans l'équipe effective)
  const unassignedByGarde = useMemo(() => {
    const map: Record<number, Personnel[]> = {}
    if (!effectiveEquipeId) return map

    const teamPersons = allPersonnels
      .filter(p => (p.equipe_id ?? null) === effectiveEquipeId)

    for (const g of filteredGardes) {
      const affs = affByGarde[g.id] || []
      const assignedIds = new Set<number>(affs.map(a => a.personnel_id))

      map[g.id] = teamPersons
        .filter(p => !assignedIds.has(p.id))
        .sort((a, b) => {
          const an = (a.nom ?? '').localeCompare(b.nom ?? '', undefined, { sensitivity: 'base' })
          if (an !== 0) return an
          return (a.prenom ?? '').localeCompare(b.prenom ?? '', undefined, { sensitivity: 'base' })
        })
    }

    return map
  }, [effectiveEquipeId, allPersonnels, filteredGardes, affByGarde])

  // ✅ rendu section GARDE / ASTREINTE
  function renderPiquetsSection(g: Garde, title: string, list: Piquet[]) {
    if (list.length === 0) return null

    return (
      <div className="pl-section">
        <div className="pl-section-title">{title}</div>

        {list.map(p => {
          const aff = affFor(g.id, p.id)
          const perso = aff ? (allPersonnels.find(x => x.id === aff.personnel_id) || null) : null
          const personaTxt = perso ? personaShort(perso) : ''

          // PRO pour cette garde ? (statut_service ou statut global)
          const isPro =
            (aff?.statut_service === 'pro') ||
            ((perso?.statut || '').toLowerCase() === 'pro')

          // 🎨 couleur de l'équipe de l'AGENT (et plus celle de la garde)
          const agentEquipeColor =
            (perso?.equipe_id && equipeColorMap[perso.equipe_id])
              ? equipeColorMap[perso.equipe_id]
              : undefined

          // pastille ovale : fond équipe de l'agent, ou violet si PRO
          const pillStyle: React.CSSProperties = aff ? {
            backgroundColor: isPro ? 'violet' : (agentEquipeColor ?? '#444'),
            color: 'black',
            borderRadius: 999,
            padding: '2px 8px',
            fontSize: '0.85rem',
            fontWeight: 600,
            display: 'inline-block',
            maxWidth: 120,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          } : {}

          return (
            <div key={p.id} className="pl-row" style={{ display: 'flex', flexWrap: 'nowrap', alignItems: 'center', gap: 6 }}>
              <div className="pl-piquet" style={{ flexShrink: 0 }}>{piquetCode(p)}</div>
              <div
                className="pl-assignee"
                title={piquetLib(p)}
                style={{ flex: '1 1 auto', minWidth: 0, overflow: 'hidden' }}
              >
                {aff ? (
                  <span className="pl-pill" style={pillStyle}>{personaTxt}</span>
                ) : (
                  <span className="pl-empty-small">—</span>
                )}
              </div>
              <div className="pl-actions" style={{ flexShrink: 0, marginLeft: 'auto' }}>
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
                      onClick={() => remove(aff)}
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
    )
  }

  // --- rendu d'une “carte garde” ---
  const renderCard = (g: Garde | null) => {
    if (!g) return null
    const cardLocked = !canModify
    const badge = g.is_holiday ? 'JF' : (g.is_weekend ? 'WE' : null)
    const unassigned = (unassignedByGarde[g.id] ?? [])

    return (
      <div key={g.id} className="pl-day" style={{ zoom }}>
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
            {renderPiquetsSection(g, 'GARDE', piquetsGarde)}

            {piquetsGarde.length > 0 && piquetsAstreinte.length > 0 && (
              <div className="pl-divider" />
            )}

            {renderPiquetsSection(g, 'ASTREINTE', piquetsAstreinte)}
          </div>

          {/* ✅ Non affectés sur cette garde */}
          {effectiveEquipeId && (
            <div className="pl-unassigned">
              <div className="pl-unassigned-head">
                <span className="pl-muted">
                  Non affectés (équipe {effectiveEquipeId}) : {unassigned.length}
                </span>
              </div>

              {unassigned.length === 0 ? (
                <div className="pl-muted" style={{ fontSize: '0.85rem' }}>
                  Tout le monde est affecté sur cette garde.
                </div>
              ) : (
                <div className="pl-unassigned-list">
                  {unassigned.map(p => {
                    const isIndispo = (indisByGarde[g.id] || []).some(i => i.personnel_id === p.id)
                    return (
                      <span
                        key={p.id}
                        className={`pl-pill${isIndispo ? ' unavail' : ''}`}
                        title={
                          canModify
                            ? (isIndispo ? 'Indisponible — cliquer pour rendre disponible' : 'Cliquer pour marquer indisponible')
                            : `${p.prenom} ${p.nom}`
                        }
                        onClick={canModify ? () => toggleIndispo(g.id, p.id) : undefined}
                        style={{
                          backgroundColor: isIndispo
                            ? 'var(--danger)'
                            : ((p.equipe_id && equipeColorMap[p.equipe_id]) ? equipeColorMap[p.equipe_id] : '#444'),
                          color: isIndispo ? '#fff' : 'black',
                          cursor: canModify ? 'pointer' : 'default',
                          borderRadius: 999,
                          padding: '3px 8px',
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: 6,
                          margin: 3,
                          maxWidth: 130,
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {isIndispo && <span style={{ flexShrink: 0 }}>🚫</span>}
                        {personaShort(p)}
                        {((p.statut || '').toLowerCase() === 'pro') && <span title="Professionnel">🟣</span>}
                      </span>
                    )
                  })}
                </div>
              )}
            </div>
          )}
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

        {(equipeId !== '' || (isChef && myEquipeId)) && (
          <button
            className="pl-btn"
            title="Télécharger la feuille de garde en PDF"
            disabled={pdfLoading}
            onClick={async () => {
              const eid = isChef ? myEquipeId : (equipeId as number)
              if (!eid) return
              setPdfLoading(true)
              try {
                await downloadPdfFeuille(year, month, eid)
              } catch (err: any) {
                alert(err?.message || "Erreur lors de la génération du PDF")
              } finally {
                setPdfLoading(false)
              }
            }}
          >
            {pdfLoading ? '…' : '📄 PDF'}
          </button>
        )}

        {/* Zoom */}
        <div className="pl-zoom-group">
          <button
            className="pl-btn pl-zoom-btn"
            title="Réduire"
            disabled={zoom <= 0.5}
            onClick={() => { const v = Math.max(0.5, Math.round((zoom - 0.1) * 10) / 10); setZoom(v); localStorage.setItem('pl-zoom', String(v)) }}
          >−</button>
          <span className="pl-zoom-label">{Math.round(zoom * 100)}%</span>
          <button
            className="pl-btn pl-zoom-btn"
            title="Agrandir"
            disabled={zoom >= 1.5}
            onClick={() => { const v = Math.min(1.5, Math.round((zoom + 0.1) * 10) / 10); setZoom(v); localStorage.setItem('pl-zoom', String(v)) }}
          >+</button>
        </div>

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
              <div className="pl-subtitle">👨‍🚒 Pro de garde</div>
              {loadingPro ? (
                <div className="pl-muted">Chargement…</div>
              ) : proDeGarde.length === 0 ? (
                <div className="pl-muted">Aucun pro de garde pour cette date</div>
              ) : (
                <div className="pl-suggests">
                  {proDeGarde.map(d => (
                    <button key={d.id} className="pl-suggest pl-suggest-pro" onClick={() => add(d.id)}>
                      {formatShortName(d.nom, d.prenom)}
                      {d.equipe_id ? <span className="pl-chip">EQ {d.equipe_id}</span> : null}
                    </button>
                  ))}
                </div>
              )}
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
              <div className="pl-subtitle">🟢 Dispo Agatt</div>
              {loadingDispos ? (
                <div className="pl-muted">Chargement…</div>
              ) : disposAgatt.length === 0 ? (
                <div className="pl-muted">Aucune dispo dans le fichier pour cette garde</div>
              ) : (
                <div className="pl-suggests">
                  {disposAgatt.map(d => (
                    <button key={d.id} className="pl-suggest pl-suggest-dispo" onClick={() => add(d.id)}>
                      {formatShortName(d.nom, d.prenom)}
                      {d.equipe_id ? <span className="pl-chip">EQ {d.equipe_id}</span> : null}
                    </button>
                  ))}
                </div>
              )}
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
                {loadingSearch ? (
                  <div className="pl-muted">Chargement…</div>
                ) : searchResults.length === 0 && search.trim() ? (
                  <div className="pl-muted">Aucun résultat</div>
                ) : (
                  searchResults.map((p: any) => (
                    <button key={p.id} className="pl-result" onClick={() => add(p.id)}>
                      {formatShortName(p.nom, p.prenom)} {p.equipe_id ? <span className="pl-chip">EQ {p.equipe_id}</span> : null}
                    </button>
                  ))
                )}
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
              <button className="pl-btn" onClick={() => confirmStatutChoice('pro')}>
                👨‍🚒 Professionnel
              </button>
              <button className="pl-btn" onClick={() => confirmStatutChoice('volontaire')}>
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
