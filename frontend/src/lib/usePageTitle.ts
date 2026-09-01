import { useEffect } from "react";

// SPA route changes are silent to screen readers by default. A per-route title is
// the standard first-line fix, and it also gives browser history usable entries
// instead of seven identical "GABAI" rows.
export function usePageTitle(title: string) {
  useEffect(() => {
    document.title = `${title} · GABAI`;
  }, [title]);
}
