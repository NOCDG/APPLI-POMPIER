import React, { useEffect, useMemo, useState } from 'react'
import {
  addCompetenceToPersonnel,
  createPersonnel,
  listCompetences,
  listEquipes,
  listPersonnels,
  listCompetencesOfPersonnel,
  deletePersonnelCompetence,
  deletePersonnel,
  deletePersonnelCompetenceByLink,
  listAllRoles,
  // 🔽 ajouts pour l’édition inline
  updatePersonnel,
  setPersonnelEquipe,
  listPersonnelRoles,
  assignRoleToPersonnel,
  removeRoleFromPersonnel,
} from '../api'
import type { Role, PersonnelCreateResponse } from '../api'
import './personnels.css'

// Récupère un "code" d'équipe à afficher (fallback vers nom)
function teamCodeFor(p: any, allTeams: any[]): string | undefined {
  return (
    p?.equipe?.code ||
    allTeams.find((t: any) => t.id === p?.equipe_id)?.code ||
    p?.equipe?.nom ||
    allTeams.find((t: any) => t.id === p?.equipe_id)?.nom ||
    undefined
  )
}

export default function PersonnelsPage() {
  const [items, setItems] = useState<any[]>([])
  const [equipes, setEquipes] = useState<any[]>([])
  const [competences, setCompetences] = useState<any[]>([])
  const [byPerson, setByPerson] = useState<Record<number, any[]>>({})

  // 🔽 rôles (options globales + rôles par personne)
  const [roleOptions, setRoleOptions] = useState<Role[]>([])
  const [byRoles, setByRoles] = useState<Record<number, Role[]>>({})

  // création
  const [selectedRoles, setSelectedRoles] = useState<Role[]>(['AGENT'])
  const [form, setForm] = useState({
    nom: '',
    prenom: '',
    grade: '',
    email: '',
    statut: 'volontaire',   // 🆕 par défaut volontaire, mais on pourra choisir "double"
    equipe_id: '' as any,
  })

  const [search, setSearch] = useState('')

  // --- ÉDITION INLINE ---
  const [editingGradeId, setEditingGradeId] = useState<number | null>(null)
  const [gradeDraft, setGradeDraft] = useState<string>('')

  const [editingEquipeId, setEditingEquipeId] = useState<number | null>(null)
  const [equipeDraft, setEquipeDraft] = useState<number | ''>('')

  const [editingRolesId, setEditingRolesId] = useState<number | null>(null)
  const [rolesDraft, setRolesDraft] = useState<Role[]>([])

  // 🆕 Édition inline du STATUT
  const [editingStatutId, setEditingStatutId] = useState<number | null>(null)
  const [statutDraft, setStatutDraft] = useState<string>('volontaire')

  // --- Modal mot de passe temporaire ---
  const [tempPasswordModal, setTempPasswordModal] = useState<{ visible: boolean; pwd?: string }>({ visible: false })
  const [pwdMasked, setPwdMasked] = useState(true)
  const [copyStatus, setCopyStatus] = useState<string | null>(null)

  async function load() {
    // charge personnels/équipes/compétences + options rôles
    const [pers, eqs, comps, rs] = await Promise.all([
      listPersonnels(),
      listEquipes(),
      listCompetences(),
      listAllRoles().catch(() => ['ADMIN','OFFICIER','OPE','CHEF_EQUIPE','ADJ_CHEF_EQUIPE','AGENT'] as Role[]),
    ])

    setItems(pers)
    setEquipes(eqs)
    setCompetences(comps)
    setRoleOptions(rs)

    // map compétences par personne
    const compMap: Record<number, any[]> = {}
    // map rôles par personne
    const roleMap: Record<number, Role[]> = {}

    await Promise.all(
      pers.map(async (p: any) => {
        try { compMap[p.id] = await listCompetencesOfPersonnel(p.id) } catch { compMap[p.id] = [] }
        try { roleMap[p.id] = await listPersonnelRoles(p.id) } catch { roleMap[p.id] = ['AGENT'] as Role[] }
      }),
    )
    setByPerson(compMap)
    setByRoles(roleMap)
  }

  useEffect(() => { load() }, [])

  // --- création ---
  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!form.nom || !form.prenom || !form.email) {
      alert('Champs requis manquants'); return
    }
    const payload = {
      ...form,
      equipe_id: form.equipe_id ? Number(form.equipe_id) : null,
      roles: selectedRoles?.length ? selectedRoles : ['AGENT'],
    }
    const res: PersonnelCreateResponse = await createPersonnel(payload as any)

    // modal mdp temporaire
    setTempPasswordModal({ visible: true, pwd: res.temp_password })
    setPwdMasked(true)
    setCopyStatus(null)

    setForm({ nom: '', prenom: '', grade: '', email: '', statut: 'volontaire', equipe_id: '' })
    setSelectedRoles(['AGENT'])
    await load()
  }

  // --- compétences ---
  async function addComp(pid: number) {
    const cid = Number((document.getElementById(`comp-${pid}`) as HTMLSelectElement).value)
    const d = (document.getElementById(`date-${pid}`) as HTMLInputElement).value || undefined
    if (!cid) { alert('Sélectionner une compétence'); return }
    await addCompetenceToPersonnel(pid, cid, d)
    const updated = await listCompetencesOfPersonnel(pid)
    setByPerson(prev => ({ ...prev, [pid]: updated }))
  }

  async function onDeletePerson(pid: number){
    if (!confirm('Supprimer ce personnel et ses liaisons de compétences ?')) return
    await deletePersonnel(pid)
    setItems(prev => prev.filter(p => p.id !== pid))
    setByPerson(prev => {
      const c = {...prev}
      delete c[pid]
      return c
    })
    setByRoles(prev => {
      const c = {...prev}
      delete c[pid]
      return c
    })
  }

  // --- édition inline : GRADE ---
  function startEditGrade(p: any){
    setEditingGradeId(p.id)
    setGradeDraft(p.grade ?? '')
  }
  async function saveGrade(p: any){
    const newGrade = (gradeDraft ?? '').trim()
    if (newGrade !== (p.grade ?? '')) {
      const updated = await updatePersonnel(p.id, { grade: newGrade })
      // sync local
      setItems(prev => prev.map(x => x.id === p.id ? { ...x, grade: updated.grade } : x))
    }
    setEditingGradeId(null)
  }

  // --- édition inline : EQUIPE ---
  function startEditEquipe(p: any){
    setEditingEquipeId(p.id)
    setEquipeDraft(p.equipe_id ?? '')
  }
  async function saveEquipe(p: any){
    const val = equipeDraft === '' ? null : Number(equipeDraft)
    await setPersonnelEquipe(p.id, val)
    setItems(prev => prev.map(x => x.id === p.id ? { ...x, equipe_id: val } : x))
    setEditingEquipeId(null)
  }

  // --- édition inline : ROLES ---
  function startEditRoles(p: any){
    setEditingRolesId(p.id)
    setRolesDraft(byRoles[p.id] ?? ['AGENT'])
  }
  async function saveRoles(p: any){
    const current = new Set(byRoles[p.id] ?? ['AGENT'])
    const next = new Set(rolesDraft.length ? rolesDraft : ['AGENT'])

    // calcul diff
    const toAdd: Role[] = []
    const toDel: Role[] = []
    next.forEach(r => { if (!current.has(r)) toAdd.push(r) })
    current.forEach(r => { if (!next.has(r)) toDel.push(r) })

    // appliquer les diffs (en série pour simplicité)
    for (const r of toAdd) await assignRoleToPersonnel(p.id, r)
    for (const r of toDel) await removeRoleFromPersonnel(p.id, r)

    // resync
    const fresh = await listPersonnelRoles(p.id).catch(()=> Array.from(next))
    setByRoles(prev => ({ ...prev, [p.id]: fresh }))
    setEditingRolesId(null)
  }

  // 🆕 édition inline : STATUT
  function startEditStatut(p: any) {
    setEditingStatutId(p.id)
    setStatutDraft(p.statut ?? 'volontaire')
  }
  async function saveStatut(p: any) {
    const newStatut = (statutDraft ?? '').trim().toLowerCase()
    if (!['pro', 'volontaire', 'double'].includes(newStatut)) {
      alert("Statut invalide (pro / volontaire / double)")
      setEditingStatutId(null)
      return
    }
    if (newStatut !== (p.statut ?? '').toLowerCase()) {
      const updated = await updatePersonnel(p.id, { statut: newStatut as any })
      setItems(prev => prev.map(x => x.id === p.id ? { ...x, statut: updated.statut } : x))
    }
    setEditingStatutId(null)
  }

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return items
    return items.filter((p: any) =>
      `${p.nom} ${p.prenom} ${p.email} ${p.grade}`.toLowerCase().includes(q),
    )
  }, [items, search])

  // Helpers affichage compétences (compat libellés/nom)
  const compCode = (pc: any) => pc?.competence?.code ?? pc?.competence?.nom ?? `#${pc?.competence_id}`
  const compLabel = (pc: any) => pc?.competence?.libelle ?? pc?.competence?.nom ?? ''

  // 🆕 helper affichage statut
  function humanStatut(st: string | undefined) {
    if (!st) return '—'
    const s = st.toLowerCase()
    if (s === 'pro') return 'Professionnel'
    if (s === 'volontaire') return 'Volontaire'
    if (s === 'double') return 'Double statut'
    return st
  }

  // Copier dans le presse-papiers (modal mdp)
  async function copyToClipboard(text: string) {
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const ta = document.createElement('textarea')
        ta.value = text
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
      }
      setCopyStatus('Copié !')
      setTimeout(() => setCopyStatus(null), 2000)
    } catch {
      setCopyStatus("Échec du copier")
      setTimeout(() => setCopyStatus(null), 2000)
    }
  }

  return (
    <div className="pg-container">
      <h2 className="pg-title">🧑‍🚒 Gestion des personnels</h2>
      <p className="pg-subtitle">Crée, recherche et enrichis les fiches agents.</p>

      {/* FORMULAIRE */}
      <section className="pg-card">
        <div className="pg-section-header">➕ Créer un personnel</div>

        <form onSubmit={onSubmit} className="pg-grid6">
          <div className="pg-field">
            <label className="pg-label">👤 Nom</label>
            <input className="pg-input" placeholder="Nom"
              value={form.nom} onChange={e => setForm({ ...form, nom: e.target.value })} />
          </div>

          <div className="pg-field">
            <label className="pg-label">🪪 Prénom</label>
            <input className="pg-input" placeholder="Prénom"
              value={form.prenom} onChange={e => setForm({ ...form, prenom: e.target.value })} />
          </div>

          <div className="pg-field">
            <label className="pg-label">🎖️ Grade</label>
            <input className="pg-input" placeholder="Grade"
              value={form.grade} onChange={e => setForm({ ...form, grade: e.target.value })} />
          </div>

          <div className="pg-field">
            <label className="pg-label">✉️ Email</label>
            <input className="pg-input" placeholder="email@exemple.fr"
              value={form.email} onChange={e => setForm({ ...form, email: e.target.value })} />
          </div>

          <div className="pg-field">
            <label className="pg-label">🏷️ Statut</label>
            <select
              className="pg-input"
              value={form.statut}
              onChange={e => setForm({ ...form, statut: e.target.value })}
            >
              <option value="volontaire">Volontaire</option>
              <option value="pro">Professionnel</option>
              {/* 🆕 troisième option */}
              <option value="double">Double statut</option>
            </select>
          </div>

          <div className="pg-field">
            <label className="pg-label">🧩 Équipe (optionnel)</label>
            <select className="pg-input" value={form.equipe_id}
              onChange={e => setForm({ ...form, equipe_id: e.target.value })}>
              <option value="">—</option>
              {equipes.map((eq: any) => (
                <option key={eq.id} value={eq.id}>
                  {(eq.code ?? eq.nom) as string}
                </option>
              ))}
            </select>
          </div>

          <div className="pg-field" style={{ gridColumn: 'span 2' }}>
            <label className="pg-label">🎚️ Rôles</label>
            <select
              multiple
              className="pg-input"
              size={Math.min(roleOptions.length || 6, 8)}
              value={selectedRoles as unknown as string[]}
              onChange={(e) => {
                const opts = Array.from(e.target.selectedOptions).map(o => o.value as Role)
                setSelectedRoles(opts.length ? opts : ['AGENT'])
              }}
              style={{ minHeight: 96 }}
            >
              {roleOptions.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
           </select>
            <small className="pg-help">Maintiens Ctrl/Cmd pour multisélection. Défaut : AGENT.</small>
          </div>

          <div className="pg-actions-right">
            <button className="pg-btn-primary" type="submit">Créer le personnel</button>
          </div>
        </form>
      </section>

      {/* RECHERCHE */}
      <section className="pg-card pg-mt-12">
        <div className="pg-section-header">🔎 Rechercher une personne</div>
        <input
          className="pg-input"
          placeholder="Nom, prénom, email, grade…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </section>

      {/* LISTE */}
      <section className="pg-list">
        {filtered.map((p: any) => {
          const pcs = byPerson[p.id] || []
          const teamCode = teamCodeFor(p, equipes)
          const rolesOfP: Role[] = byRoles[p.id] ?? ['AGENT']

          return (
            <div key={p.id} className="pg-person-card">
              <div className="pg-person-head">
                <div className="pg-person-head-left">
                  <div className="pg-avatar">{p.prenom?.[0] || '?'}{p.nom?.[0] || ''}</div>
                  <div>
                    <div className="pg-person-name">
                      {p.nom} {p.prenom}
                    </div>
                    <div className="pg-person-meta">
                      {/* Grade (inline edit) */}
                      🎖️{' '}
                      {editingGradeId === p.id ? (
                        <input
                          autoFocus
                          className="pg-input-inline"
                          value={gradeDraft}
                          onChange={e => setGradeDraft(e.target.value)}
                          onKeyDown={e => (e.key === 'Enter') && saveGrade(p)}
                          onBlur={() => saveGrade(p)}
                          placeholder="Grade"
                        />
                      ) : (
                        <span className="pg-editable" onClick={() => startEditGrade(p)}>
                          {p.grade || '—'} ✎
                        </span>
                      )}

                      {/* Équipe (inline edit) */}
                      {teamCode ? (
                        <span className={`pg-team-badge team-${String(teamCode).toLowerCase()}`}>
                          🧩
                          {editingEquipeId === p.id ? (
                            <select
                              className="pg-input-inline"
                              value={equipeDraft}
                              onChange={e => setEquipeDraft(e.target.value ? Number(e.target.value) : '')}
                              onBlur={() => saveEquipe(p)}
                              onKeyDown={e => (e.key === 'Enter') && saveEquipe(p)}
                            >
                              <option value="">—</option>
                              {equipes.map((eq: any) => (
                                <option key={eq.id} value={eq.id}>{(eq.code ?? eq.nom) as string}</option>
                              ))}
                            </select>
                          ) : (
                            <span className="pg-editable" onClick={() => startEditEquipe(p)}>
                              {' '}{String(teamCode).toUpperCase()} ✎
                            </span>
                          )}
                        </span>
                      ) : (
                        <span className="pg-team-badge">
                          🧩 {editingEquipeId === p.id ? (
                            <select
                              className="pg-input-inline"
                              value={equipeDraft}
                              onChange={e => setEquipeDraft(e.target.value ? Number(e.target.value) : '')}
                              onBlur={() => saveEquipe(p)}
                              onKeyDown={e => (e.key === 'Enter') && saveEquipe(p)}
                            >
                              <option value="">—</option>
                              {equipes.map((eq: any) => (
                                <option key={eq.id} value={eq.id}>{(eq.code ?? eq.nom) as string}</option>
                              ))}
                            </select>
                          ) : (
                            <span className="pg-editable" onClick={() => startEditEquipe(p)}>AUCUNE ✎</span>
                          )}
                        </span>
                      )}

                      {/* Statut + Rôles */}
                      {' '}• 🏷️{' '}
                      {editingStatutId === p.id ? (
                        <>
                          <select
                            className="pg-input-inline"
                            value={statutDraft}
                            onChange={e => setStatutDraft(e.target.value)}
                            onBlur={() => saveStatut(p)}
                            onKeyDown={e => (e.key === 'Enter') && saveStatut(p)}
                          >
                            <option value="volontaire">Volontaire</option>
                            <option value="pro">Professionnel</option>
                            <option value="double">Double statut</option>
                          </select>
                        </>
                      ) : (
                        <span className="pg-editable" onClick={() => startEditStatut(p)}>
                          {humanStatut(p.statut)} ✎
                        </span>
                      )}

                      {' '}• 🎭{' '}
                      {editingRolesId === p.id ? (
                        <>
                          <select
                            multiple
                            className="pg-input-inline"
                            size={Math.min(roleOptions.length || 6, 8)}
                            value={rolesDraft as unknown as string[]}
                            onChange={(e) => {
                              const vals = Array.from(e.target.selectedOptions).map(o => o.value as Role)
                              setRolesDraft(vals.length ? vals : ['AGENT'])
                            }}
                            style={{ minHeight: 96 }}
                          >
                            {roleOptions.map(r => <option key={r} value={r}>{r}</option>)}
                          </select>
                          <button className="pg-btn-mini" onClick={() => saveRoles(p)}>Sauver</button>
                          <button className="pg-btn-mini" onClick={() => setEditingRolesId(null)}>Annuler</button>
                        </>
                      ) : (
                        <span className="pg-editable" onClick={() => startEditRoles(p)}>
                          {rolesOfP.join(', ')} ✎
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* actions droite */}
                <div className="pg-person-head-actions">
                  <button className="pg-btn-danger" onClick={()=>onDeletePerson(p.id)} title="Supprimer ce personnel">
                    🗑️ Supprimer
                  </button>
                </div>
              </div>

              {/* COMPÉTENCES */}
              <div className="pg-block">
                <div className="pg-subtitle">🧠 Compétences</div>
                <div className="pg-pills">
                  {pcs.length === 0 ? (
                    <span className="pg-empty">Aucune compétence</span>
                  ) : pcs.map((pc: any) => (
                    <span key={pc.id ?? `${pc.personnel_id}-${pc.competence_id}`} className="pg-pill" title={compLabel(pc)}>
                      <span>{compCode(pc)}</span>
                      {pc.date_obtention ? <span> · {pc.date_obtention}</span> : null}
                      {pc.date_expiration ? <span> → {pc.date_expiration}</span> : null}
                      <button
                        onClick={async () => {
                          if (!confirm('Supprimer cette compétence ?')) return;
                          if (pc.id) {
                            await deletePersonnelCompetenceByLink(pc.id);
                          } else {
                            await deletePersonnelCompetence(p.id, pc.competence_id);
                          }
                          const updated = await listCompetencesOfPersonnel(p.id);
                          setByPerson(prev => ({ ...prev, [p.id]: updated }));
                        }}
                        className="pg-icon-btn"
                        title="Retirer"
                      >🗑️</button>
                    </span>
                  ))}
                </div>
              </div>

              {/* AJOUT COMPÉTENCE */}
              <div className="pg-block">
                <div className="pg-subtitle">➕ Ajouter une compétence</div>
                <div className="pg-inline">
                  <select id={`comp-${p.id}`} className="pg-input">
                    <option value="">Sélectionner…</option>
                    {competences.map((c: any) => (
                      <option key={c.id} value={c.id}>
                        {(c.code ?? c.nom) as string}
                        {c.libelle || c.description ? ` — ${c.libelle ?? c.description}` : ''}
                      </option>
                    ))}
                  </select>
                  <input id={`date-${p.id}`} type="date" className="pg-input" />
                  <button className="pg-btn-secondary" onClick={() => addComp(p.id)}>Ajouter</button>
                </div>
              </div>
            </div>
          )
        })}
      </section>

      {/* --- Modal mot de passe temporaire --- */}
      {tempPasswordModal.visible && (
        <div className="pg-modal-backdrop" onClick={() => setTempPasswordModal({ visible: false })}>
          <div className="pg-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Utilisateur créé ✓</h3>
            <p>Copie le mot de passe temporaire et transmets-le à l'agent.</p>

            <div className="pg-modal-pwd-row">
              <input
                readOnly
                value={pwdMasked ? (tempPasswordModal.pwd ?? '').replace(/./g, '•') : (tempPasswordModal.pwd ?? '')}
              />
              <button className="pg-btn-secondary" onClick={() => setPwdMasked(prev => !prev)}>
                {pwdMasked ? "👁️" : "🙈"}
              </button>
              <button
                className="pg-btn-primary"
                onClick={() => tempPasswordModal.pwd && copyToClipboard(tempPasswordModal.pwd)}
              >
                Copier
              </button>
            </div>

            {copyStatus && <div className="pg-copy-status">{copyStatus}</div>}

            <div className="pg-modal-actions">
              <button className="pg-btn" onClick={() => setTempPasswordModal({ visible: false })}>
                Fermer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
