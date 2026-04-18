import { Suspense } from "react";
import HomeClient from "./HomeClient";

export default function Home() {
  return (
    <Suspense
      fallback={
        <div className="flex h-screen items-center justify-center bg-slate-100 text-slate-600">
          Loading…
        </div>
      }
    >
      <HomeClient />
    </Suspense>
  );
}
