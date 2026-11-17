// SPDX-License-Identifier: AGPL-3.0-or-later
import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import Layout from "./components/Layout";
import AuthPage from "./pages/Auth";
import History from "./pages/History";
import Settings from "./pages/Settings";
import Studio from "./pages/Studio";
import Terms from "./pages/Terms";
import UsagePage from "./pages/Usage";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="p-8 text-center text-sm text-muted">…</div>;
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  return user ? <Navigate to="/" replace /> : <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<GuestOnly><AuthPage mode="login" /></GuestOnly>} />
          <Route path="/register" element={<GuestOnly><AuthPage mode="register" /></GuestOnly>} />
          <Route path="/terms" element={<Terms />} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route index element={<Studio />} />
            <Route path="/history" element={<History />} />
            <Route path="/usage" element={<UsagePage />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
