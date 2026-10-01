import type { ThemePreset } from "../api/types";

// Preset site colours. Each has at least 5:1 contrast with white.
// Green (GOV.UK) is the default. The server stores only the name.
export const THEMES: Record<ThemePreset, { label: string; brand: string; hover: string; edge: string }> = {
  green: { label: "Green", brand: "#00703c", hover: "#005a30", edge: "#002d18" },
  blue: { label: "Blue", brand: "#1d70b8", hover: "#144e81", edge: "#003078" },
  maroon: { label: "Maroon", brand: "#7a1e2c", hover: "#5e1622", edge: "#3d0f16" },
  teal: { label: "Teal", brand: "#00665e", hover: "#004d46", edge: "#00332f" },
  purple: { label: "Purple", brand: "#4c2c92", hover: "#3a2170", edge: "#2b1854" },
  brown: { label: "Brown", brand: "#6b4423", hover: "#52341b", edge: "#35220f" },
};

export function applyTheme(name: ThemePreset) {
  const theme = THEMES[name] ?? THEMES.green;
  const root = document.documentElement.style;
  root.setProperty("--color-brand", theme.brand);
  root.setProperty("--color-brand-hover", theme.hover);
  root.setProperty("--color-brand-edge", theme.edge);
}
