"use client";

import Directory from "@/components/Directory";

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-10">
      <h1 className="text-xl font-light">Saunas of Finland</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Every bookable sauna experience, with upcoming availability.
      </p>
      <div className="mt-6">
        <Directory />
      </div>
    </main>
  );
}
