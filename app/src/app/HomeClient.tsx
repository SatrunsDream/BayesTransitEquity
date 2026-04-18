"use client";

import dynamic from "next/dynamic";

const Dashboard = dynamic(() => import("@/components/Dashboard"), {
  ssr: false,
  loading: () => (
    <div className="flex h-screen items-center justify-center bg-slate-100 text-slate-600">
      Loading dashboard…
    </div>
  ),
});

export default function HomeClient() {
  return <Dashboard />;
}
