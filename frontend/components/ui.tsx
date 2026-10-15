"use client";
import { useId, type ReactNode } from "react";

export function Panel({ title, subtitle, children, id }: { title: string; subtitle?: string; children: ReactNode; id?: string }) {
  const heading = useId();
  return <section id={id} aria-labelledby={heading} className="min-w-0 rounded-xl border border-border bg-surface p-5 md:p-6">
    <header className="mb-5"><h2 id={heading} className="text-lg font-bold">{title}</h2>{subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}</header>{children}</section>;
}
export function MetricCard({ label, value, detail }: { label: string; value: string | number; detail: string }) {
  return <article className="rounded-xl border border-border bg-surface p-5"><h3 className="text-xs font-bold uppercase tracking-wider text-muted">{label}</h3><p className="my-3 text-3xl font-bold tabular-nums">{value}</p><p className="text-xs text-muted">{detail}</p></article>;
}
export function LoadingState({ label = "Loading match intelligence…" }: { label?: string }) {
  return <div role="status" className="rounded-xl border border-border bg-surface p-8 text-muted">{label}</div>;
}
export function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return <div role="alert" className="rounded-xl border border-border bg-surface p-6"><h2 className="font-bold">Unable to load data</h2><p className="my-3 text-sm text-muted">{message}</p><button onClick={retry} className="min-h-11 rounded-lg bg-accent px-4 font-bold text-accent-foreground">Try again</button></div>;
}
export function SelectField({ label, value, onChange, children }: { label: string; value: string | number; onChange: (value: string) => void; children: ReactNode }) {
  const id = useId();
  return <div className="min-w-0"><label className="mb-2 block text-xs font-bold uppercase tracking-wider text-muted" htmlFor={id}>{label}</label><select id={id} value={value} onChange={event => onChange(event.target.value)}>{children}</select></div>;
}
