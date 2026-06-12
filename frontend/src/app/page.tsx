"use client";

import { useState } from "react";
import Experiences from "@/components/Experiences";
import Calendar from "@/components/Calendar";

type Tab = "experiences" | "calendar";

export default function Home() {
  const [tab, setTab] = useState<Tab>("experiences");

  return (
    <main className="mx-auto max-w-3xl px-6 py-10">
      <h1 className="text-xl font-light">Sauna experiences</h1>

      <div className="mt-6 flex gap-6 border-b border-border">
        {(["experiences", "calendar"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`-mb-px border-b-2 pb-2 text-sm capitalize transition-colors ${
              tab === t
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {tab === "experiences" ? <Experiences /> : <Calendar />}
      </div>
    </main>
  );
}
