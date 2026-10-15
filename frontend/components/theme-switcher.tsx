"use client";
import { useEffect, useState } from "react";
import { useTheme } from "next-themes";

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  // Identical server/first-client markup; never infer theme during SSR.
  return <fieldset className="min-w-0"><legend className="mb-2 text-xs font-bold uppercase tracking-widest text-muted">Appearance</legend>
    <div className="flex gap-1 rounded-lg border border-border p-1">
      {["light", "dark", "system"].map(value => <button key={value} type="button" disabled={!mounted}
        aria-pressed={mounted && theme === value} onClick={() => setTheme(value)}
        className={`min-h-10 flex-1 rounded-md px-2 text-xs font-bold ${mounted && theme === value ? "bg-accent text-accent-foreground" : "text-muted hover:bg-raised"}`}>{value[0].toUpperCase() + value.slice(1)}</button>)}
    </div></fieldset>;
}
