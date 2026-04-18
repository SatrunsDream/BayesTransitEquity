"use client";

type Tone = "slate" | "blue" | "amber" | "red" | "emerald" | "violet";

const tones: Record<Tone, string> = {
  slate: "bg-slate-100 text-slate-700 border-slate-200",
  blue: "bg-blue-50 text-blue-800 border-blue-200",
  amber: "bg-amber-50 text-amber-900 border-amber-200",
  red: "bg-red-50 text-red-800 border-red-200",
  emerald: "bg-emerald-50 text-emerald-800 border-emerald-200",
  violet: "bg-violet-50 text-violet-800 border-violet-200",
};

export function Badge({
  children,
  tone = "slate",
}: {
  children: React.ReactNode;
  tone?: Tone;
}) {
  return (
    <span
      className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${tones[tone]}`}
    >
      {children}
    </span>
  );
}
