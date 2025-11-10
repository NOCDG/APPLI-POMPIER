import React, { useEffect, useMemo, useState } from 'react'
import {
  createPiquet,
  listCompetences,
  listPiquets,
  deletePiquet as apiDeletePiquet,
  addCompetenceToPiquet as apiAddCompToPiquet,   // (piquet_id, competence_id) -> PiquetRead
  removeCompetenceFromPiquet as apiDeletePiquetComp, // (piquet_id, competence_id) -> PiquetRead
  reorderPiquets, // (ids:number[]) -> PiquetRead[]
} from '../api'
import './personnels.css' // on réutilise le style

type Competence = { id:number; code?:string; libelle?:string; nom?:string; description?:string }
type PiquetRead = { id:number; code:string; libelle:string; exigences: {id:number; code?:string; libelle?:string}[] }

export default function PiquetsPage(){
  const [items,setItems]=useState<PiquetRead[]>([])
  const [competences,setCompetences]=useState<Competence[]>([])

  // form
  const [code,setCode]=useState('')
  const [libelle,setLibelle]=useState('')
  const [exigs,setExigs]=useState<number[]>([])
  const [search,setSearch]=useState('')

  // DnD state
  const [draggingId, setDraggingId] = useState<number|null>(null)

  async function load(){
    const [ps, cs] = await Promise.all([listPiquets(), listCompetences()])
    setItems(ps)
    setCompetences(cs)
  }
  useEffect(()=>{ load() },[])

  function toggle(cid:number){ setExigs(x=> x.includes(cid)? x.filter(i=>i!==cid): [...x,cid]) }

  async function onSubmit(e:React.FormEvent){
    e.preventDefault()
    if(!code.trim()||!libelle.trim()){ alert('Compléter les champs Code et Libellé'); return }
    // API: createPiquet({ code, libelle, exigences })
    const created = await createPiquet({ code: code.trim().toUpperCase(), libelle: libelle.trim(), exigences: exigs })
    setItems(prev => [...prev, created])
    setCode(''); setLibelle(''); setExigs([])
  }

  async function onDelete(pid:number){
    if(!confirm('Supprimer ce piquet ?')) return
    try {
      await apiDeletePiquet(pid)
      setItems(prev => prev.filter(p=>p.id!==pid))
    } catch(err:any){
      alert('Suppression impossible: '+(err?.message || ''))
    }
  }

  // ----- Ajout / retrait d'une compétence requise (API renvoie PiquetRead à jour) -----
  async function addExigence(pid:number, cid:number){
    if(!cid) { alert('Choisir une compétence'); return }
    try {
      const updated: PiquetRead = await apiAddCompToPiquet(pid, cid)
      setItems(prev => prev.map(p => p.id===pid ? updated : p))
    } catch(err:any){
      alert('Ajout impossible: '+(err?.message || ''))
    }
  }

  async function removeExigence(pid:number, cid:number){
    if(!confirm('Retirer cette compétence requise ?')) return
    try {
      const updated: PiquetRead = await apiDeletePiquetComp(pid, cid)
      setItems(prev => prev.map(p => p.id===pid ? updated : p))
    } catch(err:any){
      alert('Suppression impossible: '+(err?.message || ''))
    }
  }

  // ----- Réordonnancement (DnD) -----
  function onDragStartPiquet(id:number){ setDraggingId(id) }
  function onDragOverPiquet(e:React.DragEvent){ e.preventDefault() } // requis pour autoriser le drop
  function onDragEnd(){ setDraggingId(null) }

  async function onDropPiquet(targetId:number){
    if (draggingId===null || draggingId===targetId) return
    setItems(prev => {
      const from = prev.findIndex(p=>p.id===draggingId)
      const to   = prev.findIndex(p=>p.id===targetId)
      if (from<0 || to<0) return prev
      const next = prev.slice()
      const [moved] = next.splice(from,1)
      next.splice(to,0,moved)
      // Persist ordre (best effort)
      const ids = next.map(p=>p.id)
      reorderPiquets(ids).catch(()=> load())
      return next
    })
    setDraggingId(null)
  }

  const filtered = useMemo(()=>{
    const q = search.trim().toLowerCase()
    if(!q) return items
    return items.filter((p)=> `${p.code} ${p.libelle}`.toLowerCase().includes(q))
  },[items,search])

  // helpers d’affichage
  const compCode = (c: any) => c.code ?? c.nom ?? `#${c.id}`
  const compLib  = (c: any) => c.libelle ?? c.description ?? ''

  return (
    <div className="pg-container">
      <h2 className="pg-title">🚒 Gestion des piquets</h2>
      <p className="pg-subtitle">Crée, recherche, modifie les compétences requises, supprime et réordonne les piquets.</p>

      {/* FORMULAIRE */}
      <section className="pg-card">
        <div className="pg-section-header">➕ Créer un piquet</div>
        <form onSubmit={onSubmit} className="pg-grid6">
          <div className="pg-field">
            <label className="pg-label">🏷️ Code</label>
            <input className="pg-input" placeholder='Ex: VSAV-J' value={code} onChange={e=>setCode(e.target.value)} />
          </div>
          <div className="pg-field">
            <label className="pg-label">📝 Libellé</label>
            <input className="pg-input" placeholder='Ex: VSAV Jour' value={libelle} onChange={e=>setLibelle(e.target.value)} />
          </div>

          <div className="pg-field" style={{gridColumn:'1 / -1'}}>
            <label className="pg-label">🧠 Compétences requises (à la création)</label>
            <div className="pg-pills">
              {competences.map((c)=> (
                <label key={c.id} className="pg-pill" style={{cursor:'pointer'}} title={compLib(c)}>
                  <input type='checkbox' checked={exigs.includes(c.id)} onChange={()=>toggle(c.id)} />
                  <span style={{marginLeft:6}}>{compCode(c)}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="pg-actions-right">
            <button className="pg-btn-primary" type='submit'>Créer le piquet</button>
          </div>
        </form>
      </section>

      {/* RECHERCHE */}
      <section className="pg-card pg-mt-12">
        <div className="pg-section-header">🔎 Rechercher un piquet</div>
        <input className="pg-input" placeholder='Code, libellé…' value={search} onChange={e=>setSearch(e.target.value)} />
      </section>

      {/* LISTE */}
      <section className="pg-list" onDragOver={onDragOverPiquet}>
        {filtered.map((p)=>{
          // options = compétences non encore requises
          const reqIds = new Set((p.exigences||[]).map((r)=>r.id))
          const options = competences.filter((c)=> !reqIds.has(c.id))

          return (
            <div
              key={p.id}
              className="pg-person-card"
              draggable
              onDragStart={()=>onDragStartPiquet(p.id)}
              onDragEnd={onDragEnd}
              onDrop={()=>onDropPiquet(p.id)}
              style={{ opacity: draggingId===p.id ? 0.6 : 1, cursor:'grab' }}
              title="Glisser-déposer pour changer l'ordre"
            >
              <div className="pg-person-head">
                <div className="pg-person-head-left">
                  <div className="pg-avatar">{p.code?.[0] || '?'}</div>
                  <div>
                    <div className="pg-person-name">{p.code} — {p.libelle}</div>
                    <div className="pg-person-meta">ID: {p.id}</div>
                  </div>
                </div>
                <div className="pg-person-head-actions">
                  <button className="pg-btn-danger" onClick={()=>onDelete(p.id)} title="Supprimer ce piquet">🗑️ Supprimer</button>
                </div>
              </div>

              <div className="pg-block">
                <div className="pg-subtitle">📋 Compétences requises</div>
                <div className="pg-pills">
                  {(p.exigences?.length ?? 0) === 0 ? (
                    <span className="pg-empty">Aucune exigence</span>
                  ) : p.exigences.map((c)=> (
                    <span key={c.id} className="pg-pill" title={compLib(c)}>
                      {compCode(c)}
                      <button
                        className="pg-icon-btn"
                        title="Retirer"
                        onClick={()=>removeExigence(p.id, c.id)}
                      >🗑️</button>
                    </span>
                  ))}
                </div>
              </div>

              {/* Ajout d'une compétence requise */}
              <div className="pg-block">
                <div className="pg-subtitle">➕ Ajouter une exigence</div>
                <div className="pg-inline">
                  <select id={`exig-${p.id}`} className="pg-input" defaultValue="">
                    <option value="">Sélectionner…</option>
                    {options.map((c)=> (
                      <option key={c.id} value={c.id}>
                        {compCode(c)}{compLib(c) ? ` — ${compLib(c)}` : ''}
                      </option>
                    ))}
                  </select>
                  <button
                    className="pg-btn-secondary"
                    onClick={()=>{
                      const el = document.getElementById(`exig-${p.id}`) as HTMLSelectElement
                      const cid = Number(el?.value)
                      addExigence(p.id, cid)
                      if (el) el.value = ''
                    }}
                  >Ajouter</button>
                </div>
              </div>
            </div>
          )
        })}
      </section>
    </div>
  )
}
