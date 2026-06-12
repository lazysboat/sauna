"use client";

/* Read-only sauna directory: every sauna in the catalog as a card with image,
 * details and upcoming availability (open sessions). The buyer agent on :8000
 * consumes the same data and books the slots shown here. */

import { useMemo, useState } from "react";
import { Clock, Users } from "lucide-react";
import { Session, useExperiences, useSessions } from "@/lib/store";

const DATE_FMT = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
});

function slotLabel(s: Session): string {
  return `${DATE_FMT.format(new Date(s.date + "T00:00:00"))} ${s.time}`;
}

export default function Directory() {
  const [saunas, , loaded] = useExperiences();
  const [sessions] = useSessions();
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");

  const cities = useMemo(
    () => [...new Set(saunas.map((s) => s.city).filter(Boolean))].sort(),
    [saunas],
  );

  const openByExperience = useMemo(() => {
    const map = new Map<string, Session[]>();
    for (const s of sessions) {
      if (s.status !== "open") continue;
      const list = map.get(s.experienceId) ?? [];
      list.push(s);
      map.set(s.experienceId, list);
    }
    for (const list of map.values())
      list.sort((a, b) => (a.date + a.time).localeCompare(b.date + b.time));
    return map;
  }, [sessions]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return saunas.filter(
      (s) =>
        (!city || s.city === city) &&
        (!q ||
          [s.title, s.provider, s.city, s.description]
            .join(" ")
            .toLowerCase()
            .includes(q)),
    );
  }, [saunas, query, city]);

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <input
          className="input max-w-xs"
          placeholder="Search saunas…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          className="input w-auto"
          value={city}
          onChange={(e) => setCity(e.target.value)}
        >
          <option value="">All cities</option>
          {cities.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <span className="text-sm text-muted-foreground">
          {loaded ? `${visible.length} of ${saunas.length} saunas` : "loading…"}
        </span>
      </div>

      {loaded && visible.length === 0 && (
        <p className="py-12 text-center text-muted-foreground">
          No saunas match.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        {visible.map((sauna) => {
          const open = openByExperience.get(sauna.id) ?? [];
          return (
            <div
              key={sauna.id}
              className="overflow-hidden rounded border border-border transition-colors hover:bg-accent/40"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={sauna.imageUrl}
                alt={sauna.title}
                loading="lazy"
                className="aspect-[3/2] w-full object-cover"
              />
              <div className="p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate font-medium">{sauna.title}</div>
                    <div className="text-sm text-muted-foreground">
                      {sauna.provider} · {sauna.city}
                    </div>
                  </div>
                  <div className="shrink-0 text-right">
                    <div>
                      <span className="font-medium">€{sauna.priceAmount}</span>{" "}
                      <span className="text-xs text-muted-foreground">
                        / {sauna.priceUnit}
                      </span>
                    </div>
                    <div className="mt-1 flex items-center justify-end gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Users size={12} /> {sauna.capacity}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock size={12} /> {sauna.durationHours}h
                      </span>
                    </div>
                  </div>
                </div>

                <p className="mt-2 line-clamp-2 text-sm text-secondary">
                  {sauna.description}
                </p>

                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  {open.length === 0 ? (
                    <span className="text-xs text-muted-foreground">
                      Fully booked
                    </span>
                  ) : (
                    <>
                      {open.slice(0, 3).map((s) => (
                        <span
                          key={s.id}
                          className="rounded-sm border border-dashed border-primary/50 px-1.5 py-0.5 text-[11px] text-primary"
                        >
                          {slotLabel(s)}
                        </span>
                      ))}
                      {open.length > 3 && (
                        <span className="text-[11px] text-muted-foreground">
                          +{open.length - 3} more
                        </span>
                      )}
                    </>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
