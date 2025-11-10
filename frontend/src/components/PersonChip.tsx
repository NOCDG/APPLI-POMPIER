import React from 'react'
import { useDraggable } from '@dnd-kit/core'

export default function PersonChip({ id, label }: { id: string; label: string }){
  const { attributes, listeners, setNodeRef, transform } = useDraggable({ id })
  const style = transform ? { transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`} : undefined
  return (
    <div ref={setNodeRef} style={style} className="person" {...listeners} {...attributes}>
      {label}
    </div>
  )
}
