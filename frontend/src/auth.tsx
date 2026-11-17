// SPDX-License-Identifier: AGPL-3.0-or-later
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import i18n from "./i18n";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  reload: () => Promise<void>;
  setUser: (u: User | null) => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUserState] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const setUser = useCallback((u: User | null) => {
    setUserState(u);
    if (u && u.locale !== i18n.language) void i18n.changeLanguage(u.locale);
  }, []);

  const reload = useCallback(async () => {
    try {
      setUser(await api<User>("/api/me"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [setUser]);

  const logout = useCallback(async () => {
    await api("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    setUserState(null);
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return (
    <AuthContext.Provider value={{ user, loading, reload, setUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
