import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import * as api from "./api/client";
import { SessionContext } from "./session-context";
import type { User } from "./api/types";

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [initializing, setInitializing] = useState(true);

  // On first load, ask the server if a valid session cookie is already
  // attached to this browser. That's the only source of truth now.
  useEffect(() => {
    let cancelled = false;
    api.getCurrentUser().then((found) => {
      if (!cancelled) {
        setUser(found);
        setInitializing(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    const ok = await api.signIn(email, password);
    if (!ok) return false;
    const found = await api.getCurrentUser();
    setUser(found);
    return found !== null;
  }, []);

  const signOut = useCallback(async () => {
    await api.signOut();
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    const found = await api.getCurrentUser();
    setUser(found);
    return found;
  }, []);

  return (
    <SessionContext.Provider value={{ user, initializing, signIn, signOut, refresh }}>
      {children}
    </SessionContext.Provider>
  );
}