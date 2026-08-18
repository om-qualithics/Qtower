const STORAGE_KEY = "misty-theme";

export function getStoredDark(): boolean {
  if (typeof window === "undefined") return false;
  return localStorage.getItem(STORAGE_KEY) === "dark";
}

export function setStoredDark(dark: boolean): void {
  localStorage.setItem(STORAGE_KEY, dark ? "dark" : "light");
  document.documentElement.classList.toggle("dark", dark);
}

// Applied synchronously (before hydration) via an inline <script> in
// app/layout.tsx's <head> - same string, kept here as the single source of
// truth for what that script does. Avoids a flash of the wrong theme on
// every page load, not just the login page.
export const THEME_INIT_SCRIPT = `
(function () {
  try {
    var dark = localStorage.getItem("${STORAGE_KEY}") === "dark";
    if (dark) document.documentElement.classList.add("dark");
  } catch (e) {}
})();
`;
