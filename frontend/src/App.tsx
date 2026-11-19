// SPDX-License-Identifier: AGPL-3.0-or-later
import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, nextPath, useAuth } from "./auth";
import Landing from "./pages/Landing";
import Layout from "./components/Layout";
import Admin from "./pages/Admin";
import AuthPage from "./pages/Auth";
import History from "./pages/History";
import Marketing from "./pages/Marketing";
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
  const location = useLocation();
  if (loading) return null;
  return user ? <Navigate to={nextPath(location.state)} replace /> : <>{children}</>;
}

/** "/" is the studio for signed-in people and the landing page for everyone else. */
function Root() {
  const { user, loading } = useAuth();
  if (loading) return null;
  return user ? (
    <Layout>
      <Studio />
    </Layout>
  ) : (
    <Landing />
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<GuestOnly><AuthPage mode="login" /></GuestOnly>} />
          <Route path="/register" element={<GuestOnly><AuthPage mode="register" /></GuestOnly>} />
          <Route path="/" element={<Root />} />
          <Route path="/terms" element={<Terms />} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route path="/history" element={<History />} />
            <Route path="/marketing" element={<Marketing />} />
            <Route path="/credits" element={<UsagePage />} />
            <Route path="/usage" element={<Navigate to="/credits" replace />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="/admin" element={<Admin />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
