"use client";

export function LoadingSpinner({ label = "Loading map data…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 p-8 text-slate-600">
      <div        className="h-10 w-10 animate-spin rounded-full border-2 border-slate-200 border-t-blue-500"
        aria-hidden
      />
      <p className="text-sm">{label}</p>
    </div>
  );
}
