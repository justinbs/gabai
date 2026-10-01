import { useCallback, useEffect, useState } from "react";
import type { ReactNode } from "react";

import * as api from "./api/client";
import type { SiteSettings } from "./api/types";
import { SiteContext } from "./site-context";
import { applyTheme } from "./lib/themes";
import { TERMS_VERSION } from "./content/terms";

// Used until /api/site loads. Contact details are left empty.
const FALLBACK: SiteSettings = {
  barangay_name: "Barangay V (Singko)",
  place: "Amaya, Tanza, Cavite",
  address: null,
  hotline: null,
  office_hours: null,
  theme: "green",
  logo_version: null,
  terms_version: TERMS_VERSION,
  updated_at: "",
};

export function SiteProvider({ children }: { children: ReactNode }) {
  const [site, setSite] = useState<SiteSettings>(FALLBACK);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const fresh = await api.getSite();
      setSite(fresh);
      setLoaded(true);
      setFailed(false);
      return fresh;
    } catch {
      setFailed(true);
      return null;
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    applyTheme(site.theme);
  }, [site.theme]);

  const logoUrl = site.logo_version
    ? `/api/site/logo?v=${encodeURIComponent(site.logo_version)}`
    : "/barangay-logo.jpg";

  return (
    <SiteContext.Provider value={{ site, logoUrl, loaded, failed, refresh, setSite }}>
      {children}
    </SiteContext.Provider>
  );
}
