import { createContext, useContext } from "react";

import type { User } from "./api/types";

// Split from the provider so that file exports only a component. React Fast
// Refresh cannot hot-reload a file that exports other things too.

export type SessionValue = {
  user: User | null;
  signIn: (email: string) => Promise<boolean>;
  signOut: () => void;
};

export const SessionContext = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}

// For screens that only render behind a signed-in route.
export function useUser(): User {
  const { user } = useSession();
  if (!user) throw new Error("useUser used outside a protected route");
  return user;
}
