// src/auth/guards.tsx
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";
import React from "react";

type GuardProps = { children: React.ReactNode };

export function PrivateRoute({ children }: GuardProps) {
  const { user } = useAuth();
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

type RoleGuardProps = GuardProps & { roles: string[] };

export function RoleGuard({ roles, children }: RoleGuardProps) {
  const { hasAnyRole } = useAuth();
  const ok = typeof hasAnyRole === 'function' ? hasAnyRole(...roles) : false;
  return ok ? <>{children}</> : <Navigate to="/" replace />;
}
