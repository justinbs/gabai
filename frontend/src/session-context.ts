import { createContext, useContext } from "react";

import type { User } from "./api/types";

export type SessionValue = {
  user: User | null;
  initializing: boolean;
  signIn: (email: string, password: string) => Promise<boolean>;
  signOut: () => Promise<void>;
};

export const SessionContext = createContext<SessionValue | null>(null);

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession must be used inside SessionProvider");
  return value;
}

export function useUser(): User {
  const { user } = useSession();
  if (!user) throw new Error("useUser used outside a protected route");
  return user;
}