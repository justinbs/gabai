import { useEffect } from "react";

// Tagalog for the server's password messages. The server is the only place the
// rules live; this only translates. A message missing here shows in English.
const POLICY_TL: Record<string, string> = {
  "Use at least 8 characters": "Hindi bababa sa 8 karakter",
  "Use 128 characters or fewer": "Hanggang 128 karakter lang",
  "That one's too common, pick another": "Masyadong karaniwan, pumili ng iba",
  "Don't put your email in your password": "Huwag isama ang email sa password",
};

export const bilingualPolicy = (message: string) =>
  POLICY_TL[message] ? `${message} · ${POLICY_TL[message]}` : message;

// Emailed links carry the token after #, so it never reaches the server log.
// Pure on purpose: React calls state initializers twice in development, and a
// read that also cleared the hash would find nothing the second time.
export const readTokenFromHash = (): string =>
  new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";

// Then take it out of the address bar and history, since this may be the
// barangay's shared laptop.
export function useClearHash() {
  useEffect(() => {
    if (window.location.hash) {
      window.history.replaceState(null, "", window.location.pathname);
    }
  }, []);
}
