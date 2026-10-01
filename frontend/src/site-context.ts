import { createContext, useContext } from "react";

import type { SiteSettings } from "./api/types";

export type SiteValue = {
  site: SiteSettings;
  logoUrl: string;
  loaded: boolean;
  failed: boolean;
  refresh: () => Promise<SiteSettings | null>;
  setSite: (site: SiteSettings) => void;
};

export const SiteContext = createContext<SiteValue | null>(null);

export function useSite(): SiteValue {
  const value = useContext(SiteContext);
  if (!value) throw new Error("useSite must be used inside SiteProvider");
  return value;
}
