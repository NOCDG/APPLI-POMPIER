import React, { useEffect, useMemo, useState } from 'react'
import { DndContext, DragEndEvent } from '@dnd-kit/core'
import { listGardes, createAffectation } from '../api'
import { Garde } from '../types'
import DayCell, { SlotBox } from './DayCell'

function toDate(s: string){ const [y,m,d] = s.split('-').map(Number); return new Date(y, m-1, d) }

interface Props { year: number; month: number }
export default function CalendarGrid({ year, month }: Props){
  const [gardes, setGardes] = useState<Garde[]>([])
  useEffect(() => { listGardes(year, month).then(setGardes).catch(console.error) }, [year, month])

  const days = useMemo(() => {
    const map = new Map<string, Garde[]>()
    for (const g of gardes){
      const key = g.date
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(g)
    }
    return Array.from(map.entries()).sort((a,b) => a[0].localeCompare(b[0]))
  }, [gardes])

  async function onDragEnd(e: DragEndEvent){
    const { active, over } = e
    if (!over) return
    try{
      const personId = Number(String(active.id).split('-')[1])
      const [_, gardeId, piquetId] = String(over.id).split('-').map(Number)
      await createAffectation(gardeId, piquetId, personId)
      alert('Affectation OK')
    }catch(err){
      alert('Erreur affectation')
      console.error(err)
    }
  }

  return (
    <DndContext onDragEnd={onDragEnd}>
      <div className="grid">
        {days.map(([dateStr, gs]) => {
          const d = toDate(dateStr)
          const hasJour = gs.some(g => g.slot === 'JOUR')
          const gJour = gs.find(g => g.slot === 'JOUR')
          const gNuit = gs.find(g => g.slot === 'NUIT')!
          return (
            <DayCell key={dateStr} date={d} isWeekend={gNuit.is_weekend} isHoliday={gNuit.is_holiday}>
              {hasJour && <SlotBox id={`drop-${gJour!.id}-1`} title="JOUR — Piquet 1" />}
              <SlotBox id={`drop-${gNuit.id}-1`} title="NUIT — Piquet 1" />
            </DayCell>
          )
        })}
      </div>
    </DndContext>
  )
}
