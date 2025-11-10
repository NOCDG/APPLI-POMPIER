import React, { useEffect, useMemo, useState } from 'react'
import { createEquipe, listEquipes, updateEquipe, deleteEquipe } from '../api'
import './personnels.css' // réutilise le style commun

export default function EquipesPage(){
  const [items,setItems] = useState<any[]>([])
  const [code,setCode]=useState('')
  const [libelle,setLibelle]=useState('')
  const [couleur,setCouleur]=useState('#888888')
  const [search,setSearch]=useState('')

  // édition inline
  const [editingId,setEditingId]=useState<number|null>(null)
  const [edit,setEdit]=useState({ code:'', libelle:'', couleur:'#888888' })

  async function load(){ setItems(await listEquipes()) }
  useEffect(()=>{ load() },[])

  async function onSubmit(e:React.FormEvent){
    e.preventDefault()
    if(!code.trim()||!libelle.trim()){ alert('Compléter Code + Libellé'); return }
    await createEquipe({ code:code.trim().toUpperCase(), libelle:libelle.trim(), couleur })
    setCode(''); setLibelle(''); setCouleur('#888888')
    await load()
  }

  function startEdit(e:any){
    setEditingId(e.id)
    setEdit({ code:e.code, libelle:e.libelle, couleur:e.couleur || '#888888' })
  }
  function cancelEdit(){ setEditingId(null) }

  async function saveEdit(id:number){
    if(!edit.code.trim() || !edit.libelle.trim()){ alert('Compléter Code + Libellé'); return }
    await updateEquipe(id, {
      code: edit.code.trim().toUpperCase(),
      libelle: edit.libelle.trim(),
      couleur: edit.couleur || '#888888'
    })
    setEditingId(null)
    await load()
  }

  async function onDelete(id:number){
    if(!confirm('Supprimer cette équipe ?')) return
    try{
      await deleteEquipe(id)
      setItems(prev=> prev.filter(x=>x.id!==id))
    }catch(err:any){
      alert(err?.message || 'Suppression impossible')
    }
  }

  const filtered = useMemo(()=>{
    const q = search.trim().toLowerCase()
    if(!q) return items
    return items.filter((e:any)=> `${e.code} ${e.libelle}`.toLowerCase().includes(q))
  },[items,search])

  return (
    <div className="pg-container">
      <h2 className="pg-title">🧩 Gestion des équipes</h2>
      <p className="pg-subtitle">Crée, recherche, modifie et supprime des équipes.</p>

      {/* FORMULAIRE de création */}
      <section className="pg-card">
        <div className="pg-section-header">➕ Créer une équipe</div>
        <form onSubmit={onSubmit} className="pg-grid6" style={{alignItems:'end'}}>
          <div className="pg-field">
            <label className="pg-label">🏷️ Code (A/B/C/D)</label>
            <input className="pg-input" placeholder="A" value={code} onChange={e=>setCode(e.target.value)} />
          </div>
          <div className="pg-field">
            <label className="pg-label">📝 Libellé</label>
            <input className="pg-input" placeholder="Equipe A" value={libelle} onChange={e=>setLibelle(e.target.value)} />
          </div>
          <div className="pg-field">
            <label className="pg-label">🎨 Couleur</label>
            <input type="color" className="pg-input" value={couleur} onChange={e=>setCouleur(e.target.value)} />
          </div>
          <div className="pg-actions-right">
            <button className="pg-btn-primary" type="submit">Créer l’équipe</button>
          </div>
        </form>
      </section>

      {/* RECHERCHE */}
      <section className="pg-card pg-mt-12">
        <div className="pg-section-header">🔎 Rechercher une équipe</div>
        <input className="pg-input" placeholder="Code, libellé…" value={search} onChange={e=>setSearch(e.target.value)} />
      </section>

      {/* LISTE */}
      <section className="pg-list">
        {filtered.map((e:any)=>(
          <div key={e.id} className="pg-person-card">
            <div className="pg-person-head">
              <div className="pg-person-head-left">
                <span style={{
                  display:'inline-block', width:36, height:36, borderRadius:999,
                  background: e.couleur || '#888888', marginRight:10
                }} />
                {editingId===e.id ? (
                  <div className="pg-inline" style={{flexWrap:'wrap'}}>
                    <input className="pg-input" style={{minWidth:120}}
                      value={edit.code} onChange={ev=>setEdit(s=>({...s, code:ev.target.value}))} />
                    <input className="pg-input" style={{minWidth:220}}
                      value={edit.libelle} onChange={ev=>setEdit(s=>({...s, libelle:ev.target.value}))} />
                    <input type="color" className="pg-input"
                      value={edit.couleur} onChange={ev=>setEdit(s=>({...s, couleur:ev.target.value}))} />
                  </div>
                ) : (
                  <div>
                    <div className="pg-person-name">
                      <b>{e.code}</b> — {e.libelle}
                    </div>
                    <div className="pg-person-meta">Couleur: {e.couleur}</div>
                  </div>
                )}
              </div>

              <div className="pg-person-head-actions">
                {editingId===e.id ? (
                  <>
                    <button className="pg-btn-secondary" onClick={()=>saveEdit(e.id)}>💾 Enregistrer</button>
                    <button className="pg-btn-secondary" onClick={cancelEdit}>↩️ Annuler</button>
                  </>
                ) : (
                  <>
                    <button className="pg-btn-secondary" onClick={()=>startEdit(e)}>✏️ Modifier</button>
                    <button className="pg-btn-danger" onClick={()=>onDelete(e.id)}>🗑️ Supprimer</button>
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
