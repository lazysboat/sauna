"use client";

/* Read-only sauna directory: every sauna in the catalog as a card with image,
 * details and upcoming availability (open sessions). Clicking a card opens its
 * full schedule. The buyer agent on :8000 consumes the same data and books the
 * slots shown here. */

import { useMemo, useState } from "react";
import { Clock, Users, X } from "lucide-react";
import { Experience, Session, useExperiences, useSessions } from "@/lib/store";

const DATE_FMT = new Intl.DateTimeFormat("en-GB", {
  weekday: "short",
  day: "numeric",
  month: "short",
});

function dayLabel(date: string): string {
  return DATE_FMT.format(new Date(date + "T00:00:00"));
}

function slotLabel(s: Session): string {
  return `${dayLabel(s.date)} ${s.time}`;
}

export default function Directory() {
  const [saunas, , loaded] = useExperiences();
  const [sessions] = useSessions();
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [selected, setSelected] = useState<Experience | null>(null);

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
              onClick={() => setSelected(sauna)}
              className="cursor-pointer overflow-hidden rounded border border-border transition-colors hover:bg-accent/40"
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

      {selected && (
        <AvailabilityPanel
          sauna={selected}
          sessions={sessions.filter((s) => s.experienceId === selected.id)}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

function AvailabilityPanel({
  sauna,
  sessions,
  onClose,
}: {
  sauna: Experience;
  sessions: Session[];
  onClose: () => void;
}) {
  const byDay = useMemo(() => {
    const map = new Map<string, Session[]>();
    for (const s of sessions) {
      const list = map.get(s.date) ?? [];
      list.push(s);
      map.set(s.date, list);
    }
    return [...map.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, list]) => ({
        date,
        slots: list.sort((a, b) => a.time.localeCompare(b.time)),
      }));
  }, [sessions]);

  const openCount = sessions.filter((s) => s.status === "open").length;

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-foreground/20 p-4"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="flex max-h-[80vh] w-full max-w-md flex-col rounded-lg border border-border bg-background shadow-lg"
      >
        <div className="flex items-start justify-between gap-3 border-b border-border p-4">
          <div className="min-w-0">
            <div className="truncate font-medium">{sauna.title}</div>
            <div className="text-sm text-muted-foreground">
              {sauna.provider} · {sauna.city}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <span className="text-sm">
              <span className="font-medium">€{sauna.priceAmount}</span>{" "}
              <span className="text-xs text-muted-foreground">
                / {sauna.priceUnit}
              </span>
            </span>
            <button
              onClick={onClose}
              className="rounded-sm p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
              title="Close"
            >
              <X size={16} />
            </button>
          </div>
        </div>

        <div className="overflow-y-auto p-4">
          <div className="mb-3 text-sm text-secondary">
            {openCount === 0
              ? "Fully booked for the next three weeks."
              : `${openCount} open ${openCount === 1 ? "slot" : "slots"} in the next three weeks.`}
          </div>

          <div className="space-y-3">
            {byDay.map(({ date, slots }) => (
              <div key={date}>
                <div className="mb-1 text-xs uppercase tracking-wider text-muted-foreground">
                  {dayLabel(date)}
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {slots.map((s) =>
                    s.status === "open" ? (
                      <span
                        key={s.id}
                        className="rounded-sm border border-dashed border-primary/50 px-2 py-0.5 text-xs text-primary"
                      >
                        {s.time}
                      </span>
                    ) : (
                      <span
                        key={s.id}
                        className="rounded-sm bg-[rgba(242,241,238,0.6)] px-2 py-0.5 text-xs text-muted-foreground line-through"
                      >
                        {s.time}
                      </span>
                    ),
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 flex gap-4 border-t border-border pt-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-6 rounded-sm border border-dashed border-primary/50" />
              open
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-3 w-6 rounded-sm bg-[rgba(242,241,238,0.9)]" />
              booked
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
