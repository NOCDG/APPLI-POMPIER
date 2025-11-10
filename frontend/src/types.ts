export type Slot = 'JOUR' | 'NUIT'
export interface Garde { id: number; date: string; slot: Slot; is_weekend: boolean; is_holiday: boolean }
export interface Personnel { id: number; nom: string; prenom: string; grade: string; email: string; statut: string; equipe_id?: number | null }
export interface Piquet { id: number; code: string; libelle: string }
