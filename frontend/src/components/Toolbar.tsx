import React from 'react'

interface Props { month: number; year: number; onPrev(): void; onNext(): void; onGenerate(): void }
export default function Toolbar({ month, year, onPrev, onNext, onGenerate }: Props){
  const label = new Date(year, month-1, 1).toLocaleDateString('fr-FR', { month:'long', year:'numeric' })
  return (
    <div className="header">
      <h1 style={{margin:0}}>Planning — {label}</h1>
      <div className="toolbar">
        <button className="btn" onClick={onPrev}>◀︎</button>
        <button className="btn" onClick={onNext}>▶︎</button>
        <button className="btn" onClick={onGenerate}>Générer le mois</button>
      </div>
    </div>
  )
}
