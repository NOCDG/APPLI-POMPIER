import React from 'react'
import { useDroppable } from '@dnd-kit/core'

export function SlotBox({ id, title }: { id: string; title: string }){
  const { isOver, setNodeRef } = useDroppable({ id })
  return (
    <div ref={setNodeRef} className="slot" style={{ background: isOver ? '#0e1b3f' : undefined }}>
      <div className="slot-title">{title}</div>
    </div>
  )
}

export default function DayCell({ date, isWeekend, isHoliday, children }: React.PropsWithChildren<{ date: Date; isWeekend: boolean; isHoliday: boolean }>) {
  const label = new Intl.DateTimeFormat('fr-FR', { day:'2-digit' }).format(date)
  const deco = isHoliday ? '★ ' : ''
  return (
    <div className="day">
      <div className="legend">{deco}{label} {isWeekend ? '(WE)' : ''}</div>
      {children}
    </div>
  )
}
