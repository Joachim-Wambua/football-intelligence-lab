"use client";
import { useState, type ReactNode } from "react";
import { ThemeSwitcher } from "./theme-switcher";

export function Shell({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
    <a href="#main-content" className="sr-only z-50 rounded bg-accent p-3 text-accent-foreground focus:not-sr-only focus:fixed focus:left-4 focus:top-4">Skip to content</a>
    <aside className="border-b border-border bg-surface lg:sticky lg:top-0 lg:h-screen lg:border-r lg:border-b-0">
      <div className="flex items-center justify-between gap-3 p-6"><a href="/" className="flex items-center gap-3 font-bold leading-tight"><span aria-hidden="true" className="grid h-10 w-10 place-items-center rounded-lg bg-accent text-accent-foreground">FI</span><span>Football<br/>Intelligence Lab<span className="mt-1 block text-[10px] uppercase tracking-widest text-muted">The analyst workspace</span></span></a>
        <button className="min-h-11 rounded border border-border px-3 lg:hidden" aria-expanded={open} aria-controls="workspace-navigation" onClick={() => setOpen(!open)}>{open ? "Close" : "Menu"}</button></div>
      <div id="workspace-navigation" className={`${open ? "block" : "hidden"} px-5 pb-6 lg:flex lg:h-[calc(100%-108px)] lg:flex-col`}>
        <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[.2em] text-muted">Workspace / 01</p>
        <nav aria-label="Workspace" className="space-y-2">{[["overview", "Match overview", "01"], ["players", "Player comparison", "02"], ["passes", "Passing intelligence", "03"], ["shots", "Shot map", "04"], ["insights", "Match insights", "05"], ["expected-threat", "Expected Threat", "06"]].map(([id, label, number]) => <a key={id} href={`#${id}`} onClick={() => setOpen(false)} className="flex min-h-12 items-center gap-3 rounded-lg px-3 text-sm font-bold hover:bg-raised"><span className="text-xs text-muted">{number}</span>{label}</a>)}</nav>
        <div className="mt-8 space-y-5 lg:mt-auto"><div className="rounded-lg border border-border p-3 text-xs leading-relaxed text-muted">Built on StatsBomb open data.<br/>Research backed. Match focused.</div><ThemeSwitcher/></div>
      </div></aside>
    <main id="main-content" tabIndex={-1} className="min-w-0 p-4 sm:p-7 xl:p-10">{children}</main>
  </div>;
}
