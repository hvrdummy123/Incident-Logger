export type Theme = "light" | "dark" | "system";

const KEY = "traceiq.theme";

export function readTheme(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {
    /* ignore */
  }
  return "system";
}

export function writeTheme(theme: Theme): void {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* ignore */
  }
  applyTheme(theme);
}

export function applyTheme(theme: Theme = readTheme()): void {
  const root = document.documentElement;
  if (theme === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", theme);
  }
}

export function cycleTheme(current: Theme): Theme {
  const next: Theme = current === "dark" ? "light" : current === "light" ? "system" : "dark";
  writeTheme(next);
  return next;
}
