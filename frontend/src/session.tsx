import { useCallback, useState } from "react";
import type { ReactNode } from "react";

import * as api from "./api/client";
import { SessionContext } from "./session-context";
import type { User } from "./api/types";

// Real auth is a session cookie the browser holds. Until the backend exists the
// signed-in email lives in sessionStorage so a refresh does not sign you out.

const STORAGE_KEY = "gabai.email";

const readStored = (): User | undefined => {
  try {
    const email = sessionStorage.getItem(STORAGE_KEY);
    return email ? api.userByEmail(email) : undefined;
  } catch {
    // Private browsing and blocked site data both throw here.
    return undefined;
  }
};

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => readStored() ?? null);

  const signIn = useCallback(async (email: string) => {
    const found = await api.signIn(email);
    if (!found) return false;
    try {
      sessionStorage.setItem(STORAGE_KEY, found.email);
    } catch {
      // Non-fatal, the session just will not survive a refresh.
    }
    setUser(found);
    return true;
  }, []);

  const signOut = useCallback(() => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch {
      // Ignored, as above.
    }
    // No reset here. Signing out and back in as someone else is how you follow a
    // request from resident to staff, and how you check that deactivating an
    // account actually blocks it. A page reload re-seeds the fixtures.
    setUser(null);
  }, []);

  return (
    <SessionContext.Provider value={{ user, signIn, signOut }}>
      {children}
    </SessionContext.Provider>
  );
}
