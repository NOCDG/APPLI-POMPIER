// src/App.tsx
import React, { useEffect, useState } from 'react'
import './styles.css'
import Nav from './components/Nav'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import CompetencesPage from './pages/CompetencesPage'
import PiquetsPage from './pages/PiquetsPage'
import EquipesPage from './pages/EquipesPage'
import PersonnelsPage from './pages/PersonnelsPage'
import Toolbar from './components/Toolbar'
import CalendarGrid from './components/CalendarGrid'
import PersonChip from './components/PersonChip'
import PlanningPage from './pages/PlanningPage'
import SaisieGardesPage from './pages/SaisieGardesPage'
import VisionGardesPage from './pages/VisionGardesPage'
import { listPersonnels, generateMonth } from './api'
import EquipeCalendarPage from './pages/EquipeCalendarPage'
import Login from './pages/Login'
import ProtectedRoute from './auth/ProtectedRoute'
import { AuthProvider } from './auth/AuthContext'
import Home from './pages/Home'
import { RoleGuard } from './auth/guards'
import AdminSettingsPage from './pages/AdminSettingsPage'
import ForgotPassword from "./pages/ForgotPassword"
import ResetPassword from "./pages/ResetPassword"
import { ThemeProvider } from './ThemeContext'

/** Enveloppe commune : Nav sticky + contenu centré */
function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="shell">
      <Nav />
      <div className="shell-content">
        {children}
      </div>
    </div>
  )
}

function CalendarView() {
  const now = new Date()
  const [month, setMonth] = useState(now.getMonth() + 1)
  const [year, setYear] = useState(now.getFullYear())
  const [people, setPeople] = useState<any[]>([])

  useEffect(() => {
    listPersonnels().then(setPeople).catch(console.error)
  }, [])

  return (
    <>
      <Toolbar
        month={month}
        year={year}
        onPrev={() => {
          const d = new Date(year, month - 2, 1)
          setYear(d.getFullYear())
          setMonth(d.getMonth() + 1)
        }}
        onNext={() => {
          const d = new Date(year, month, 1)
          setYear(d.getFullYear())
          setMonth(d.getMonth() + 1)
        }}
        onGenerate={() => generateMonth(year, month).then(() => window.location.reload())}
      />
      <div className="layout">
        <aside className="sidebar">
          <h3>Personnel</h3>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {people.map((p) => (
              <PersonChip key={p.id} id={`person-${p.id}`} label={`${p.nom} ${p.prenom}`} />
            ))}
          </div>
        </aside>
        <main>
          <CalendarGrid year={year} month={month} />
        </main>
      </div>
    </>
  )
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route path="/" element={
        <ProtectedRoute>
          <AppShell><Home /></AppShell>
        </ProtectedRoute>
      } />

      <Route path="/calendrier" element={
        <ProtectedRoute>
          <RoleGuard roles={['ADMIN', 'OFFICIER', 'OPE']}>
            <AppShell><CalendarView /></AppShell>
          </RoleGuard>
        </ProtectedRoute>
      } />

      <Route path="/personnels" element={
        <ProtectedRoute>
          <RoleGuard roles={['ADMIN', 'OFFICIER', 'OPE']}>
            <AppShell><PersonnelsPage /></AppShell>
          </RoleGuard>
        </ProtectedRoute>
      } />

      <Route path="/equipes" element={
        <ProtectedRoute>
          <RoleGuard roles={['ADMIN', 'OFFICIER', 'OPE']}>
            <AppShell><EquipesPage /></AppShell>
          </RoleGuard>
        </ProtectedRoute>
      } />

      <Route path="/competences" element={
        <ProtectedRoute>
          <RoleGuard roles={['ADMIN', 'OFFICIER', 'OPE']}>
            <AppShell><CompetencesPage /></AppShell>
          </RoleGuard>
        </ProtectedRoute>
      } />

      <Route path="/piquets" element={
        <ProtectedRoute>
          <RoleGuard roles={['ADMIN', 'OFFICIER', 'OPE']}>
            <AppShell><PiquetsPage /></AppShell>
          </RoleGuard>
        </ProtectedRoute>
      } />

      <Route path="/planning" element={
        <ProtectedRoute>
          <RoleGuard roles={['ADMIN', 'OFFICIER', 'OPE', 'CHEF_EQUIPE', 'ADJ_CHEF_EQUIPE']}>
            <AppShell><PlanningPage /></AppShell>
          </RoleGuard>
        </ProtectedRoute>
      } />

      <Route path="/calendrier-equipe" element={
        <ProtectedRoute>
          <RoleGuard roles={['ADMIN', 'OFFICIER', 'OPE']}>
            <AppShell><EquipeCalendarPage /></AppShell>
          </RoleGuard>
        </ProtectedRoute>
      } />

      <Route path="/saisies-gardes" element={
        <ProtectedRoute>
          <RoleGuard roles={['ADMIN', 'OFFICIER', 'OPE']}>
            <AppShell><SaisieGardesPage /></AppShell>
          </RoleGuard>
        </ProtectedRoute>
      } />

      <Route path="/vision-gardes" element={
        <ProtectedRoute>
          <RoleGuard roles={['ADMIN', 'OFFICIER', 'OPE', 'AGENT']}>
            <AppShell><VisionGardesPage /></AppShell>
          </RoleGuard>
        </ProtectedRoute>
      } />

      <Route path="/admin/settings" element={
        <ProtectedRoute>
          <RoleGuard roles={['ADMIN']}>
            <AppShell><AdminSettingsPage /></AppShell>
          </RoleGuard>
        </ProtectedRoute>
      } />

      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  )
}
