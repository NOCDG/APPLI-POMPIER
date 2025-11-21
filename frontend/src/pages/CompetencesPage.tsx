import React, { useEffect, useMemo, useState } from 'react'
import { createCompetence, listCompetences, /* facultatifs si existants: */ updateCompetence as apiUpdateCompetence, deleteCompetence as apiDeleteCompetence } from '../api'
import './equipe-calendar.css'

export default function CompetencesPage(){
  const [items, setItems] = useState<any[]>([])
  const [code,setCode] = useState('')
  const [libelle,setLibelle] = useState('')
  const [search, setSearch] = useState('')

  // État d'édition
  const [editingId, setEditingId] = useState<number|null>(null)
  const [editCode, setEditCode] = useState('')
  const [editLibelle, setEditLibelle] = useState('')

  async function load(){ setItems(await listCompetences()) }
  useEffect(()=>{ load() },[])

  async function onSubmit(e:React.FormEvent){
    e.preventDefault()
    if(!code.trim()||!libelle.trim()){ alert('Compléter les champs'); return }
    await createCompetence({code:code.trim().toUpperCase(), libelle:libelle.trim()})
    setCode(''); setLibelle(''); await load()
  }

  // --- Edition ---
  function beginEdit(c:any){
    setEditingId(c.id); setEditCode(c.code); setEditLibelle(c.libelle)
  }
  async function saveEdit(){
    if(!editingId) return
    if(!editCode.trim()||!editLibelle.trim()){ alert('Compléter les champs'); return }
    try{
      if (typeof apiUpdateCompetence === 'function') {
        await apiUpdateCompetence(editingId, { code: editCode.trim().toUpperCase(), libelle: editLibelle.trim() })
      } else {
        await fetch(`${import.meta.env.VITE_API_URL}/competences/${editingId}`, {
          method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ code: editCode.trim().toUpperCase(), libelle: editLibelle.trim() })
        })
      }
      setEditingId(null); setEditCode(''); setEditLibelle(''); await load()
    }catch(err:any){ alert('Échec de la modification: '+(err?.message||'inconnu')) }
  }
  function cancelEdit(){ setEditingId(null); setEditCode(''); setEditLibelle('') }

  // --- Suppression ---
  async function removeCompetence(id:number){
    if(!confirm('Supprimer cette compétence ?')) return
    try{
      if (typeof apiDeleteCompetence === 'function') {
        await apiDeleteCompetence(id)
      } else {
        await fetch(`${import.meta.env.VITE_API_URL}/competences/${id}`, { method:'DELETE' })
      }
      // rafraîchissement optimiste
      setItems(prev=>prev.filter(x=>x.id!==id))
    }catch(err:any){ alert('Suppression impossible: '+(err?.message||'inconnu')) }
  }

  const filtered = useMemo(()=>{
    const q = search.trim().toLowerCase()
    if(!q) return items
    return items.filter((c:any)=> `${c.code} ${c.libelle}`.toLowerCase().includes(q))
  },[items,search])

  return (
    <div className="pg-container">
      <h2 className="pg-title">🧠 Gestion des compétences</h2>
      <p className="pg-subtitle">Crée, recherche, modifie et supprime des compétences.</p>

      {/* FORMULAIRE */}
      <section className="pg-card">
        <div className="pg-section-header">➕ Créer une compétence</div>
        <form onSubmit={onSubmit} className="pg-grid6">
          <div className="pg-field">
            <label className="pg-label">🏷️ Code</label>
            <input className="pg-input" placeholder='Ex: SOG' value={code} onChange={e=>setCode(e.target.value)} />
          </div>
          <div className="pg-field">
            <label className="pg-label">📝 Libellé</label>
            <input className="pg-input" placeholder='Libellé' value={libelle} onChange={e=>setLibelle(e.target.value)} />
          </div>
          <div className="pg-actions-right">
            <button className="pg-btn-primary" type='submit'>Créer la compétence</button>
          </div>
        </form>
      </section>

      {/* RECHERCHE */}
      <section className="pg-card pg-mt-12">
        <div className="pg-section-header">🔎 Rechercher</div>
        <input className="pg-input" placeholder='Code, libellé…' value={search} onChange={e=>setSearch(e.target.value)} />
      </section>

      {/* LISTE */}
      <section className="pg-list">
        {filtered.map((c:any)=> (
          <div key={c.id} className="pg-person-card">
            <div className="pg-person-head">
              <div className="pg-person-head-left">
                <div className="pg-avatar">{c.code?.[0] || '?'}</div>
                <div>
                  {editingId===c.id ? (
                    <>
                      <div className="pg-inline" style={{marginBottom:6}}>
                        <input className="pg-input" value={editCode} onChange={e=>setEditCode(e.target.value)} placeholder='Code' />
                        <input className="pg-input" value={editLibelle} onChange={e=>setEditLibelle(e.target.value)} placeholder='Libellé' />
                      </div>
                      <div className="pg-inline">
                        <button className="pg-btn-primary" onClick={saveEdit}>💾 Enregistrer</button>
                        <button className="pg-btn-secondary" onClick={cancelEdit}>↩️ Annuler</button>
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="pg-person-name">{c.code} — {c.libelle}</div>
                      <div className="pg-person-meta">ID: {c.id}</div>
                    </>
                  )}
                </div>
              </div>
              <div className="pg-person-head-actions">
                {editingId===c.id ? null : (
                  <>
                    <button className="pg-btn-secondary" onClick={()=>beginEdit(c)}>✏️ Modifier</button>
                    <button className="pg-btn-danger" onClick={()=>removeCompetence(c.id)}>🗑️ Supprimer</button>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}
      </section>
    </div>
  )
}
