// SPDX-License-Identifier: AGPL-3.0-or-later
import { useEffect, type ReactNode } from "react";
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
  const location = useLocation();
  if (loading) return <div className="p-8 text-center text-sm text-muted">…</div>;
  // Remember where the person wanted to go, so sign-in lands there (nextPath reads `state.next`).
  return user ? <>{children}</> : <Navigate to="/login" replace state={{ next: location.pathname }} />;
}

/** New page = top of the page (the router does not reset scroll on its own). Hash links keep working. */
function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    if (!window.location.hash) window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function GuestOnly({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return null;
  return user ? <Navigate to={nextPath(location.state)} replace /> : <>{children}</>;
}

function StudioRedirect() {
  const location = useLocation();
  return <Navigate to="/create" replace state={location.state} />;
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ScrollToTop />
        <Routes>
          <Route path="/login" element={<GuestOnly><AuthPage mode="login" /></GuestOnly>} />
          <Route path="/register" element={<GuestOnly><AuthPage mode="register" /></GuestOnly>} />
          <Route path="/" element={<Landing />} />
          {/* Generation lives at /create, not on the homepage. "/studio" is an alias; router state (remix, prefill) is kept. */}
          <Route path="/studio" element={<StudioRedirect />} />
          <Route path="/terms" element={<Terms />} />
          <Route element={<RequireAuth><Layout /></RequireAuth>}>
            <Route path="/create" element={<Studio />} />
            <Route path="/history" element={<History />} />
            <Route path="/library" element={<History />} />
            <Route path="/marketing" element={<Marketing />} />
            <Route path="/credits" element={<UsagePage />} />
            <Route path="/pricing" element={<UsagePage />} />
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
