"use client";

export function StatCard({
  label,
  value,
  sub,
  warn,
}: {
  label: string;
  value: React.ReactNode;
  sub?: string;
  warn?: boolean;
}) {
  return (
    <div
      className={`rounded-lg border bg-white p-3 shadow-sm ${warn ? "border-amber-300 ring-1 ring-amber-100" : "border-slate-200"}`}
    >
      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">
        {label}
      </div>
      <div className="mt-1 text-xl font-bold tabular-nums text-slate-900">{value}</div>
      {sub ? <div className="mt-0.5 text-xs text-slate-500">{sub}</div> : null}
    </div>
  );
}
