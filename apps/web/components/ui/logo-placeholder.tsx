// Rendered wherever a catalog card would show a real logo but logo_url
// is null - required for every existing tool/vendor on migration day,
// not just new ones. Same "initials in a colored square" visual weight
// as app-shell.tsx's org-logo fallback, generalized to any name.
export function LogoPlaceholder({ name, className = "h-8 w-8" }: { name: string; className?: string }) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <div
      className={`flex shrink-0 items-center justify-center rounded-lg bg-secondary text-sm font-semibold text-secondary-foreground ${className}`}
    >
      {initial}
    </div>
  );
}
