"use client";

/* The data seam (SPEC §6 / HANDOVER §2). Components consume data ONLY through
 * useExperiences() / useSessions(), each returning [items, setItems, loaded].
 * This implementation is API-backed (FastAPI on :8000): load on mount, then
 * every setItems applies optimistically and diff-syncs the change to the API
 * (new/changed ids → POST/PUT, removed ids → DELETE). */

import { useCallback, useEffect, useRef, useState } from "react";

export type PriceUnit = "booking" | "person";
export type ExperienceStatus = "published" | "paused";
export type Experience = {
  id: string;
  title: string;
  provider: string;
  city: string;
  location: string;
  description: string;
  imageUrl: string;
  priceAmount: number;
  priceUnit: PriceUnit;
  capacity: number;
  durationHours: number;
  status: ExperienceStatus;
};

export type SessionStatus = "open" | "booked";
export type Session = {
  id: string;
  experienceId: string;
  date: string; // "yyyy-MM-dd"
  time: string; // "HH:MM"
  status: SessionStatus;
};

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function randomId(prefix: string): string {
  return `${prefix}-${Math.random().toString(16).slice(2, 8)}`;
}

type WithId = { id: string };
type SetList<T> = (next: T[] | ((prev: T[]) => T[])) => void;

async function request(path: string, method: string, body?: unknown) {
  try {
    await fetch(`${API_BASE}${path}`, {
      method,
      headers: body ? { "content-type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (e) {
    console.error(`API ${method} ${path} failed`, e);
  }
}

/** Push the difference between prev and next to the API. Lists are tiny. */
function syncDiff<T extends WithId>(path: string, prev: T[], next: T[]) {
  const prevById = new Map(prev.map((i) => [i.id, i]));
  const nextIds = new Set(next.map((i) => i.id));
  for (const item of next) {
    const old = prevById.get(item.id);
    if (!old) void request(path, "POST", item);
    else if (JSON.stringify(old) !== JSON.stringify(item))
      void request(`${path}/${item.id}`, "PUT", item);
  }
  for (const old of prev) {
    if (!nextIds.has(old.id)) void request(`${path}/${old.id}`, "DELETE");
  }
}

function useApiList<T extends WithId>(path: string): [T[], SetList<T>, boolean] {
  const [items, setItemsState] = useState<T[]>([]); // [] on SSR + first paint
  const [loaded, setLoaded] = useState(false);
  const itemsRef = useRef(items);
  itemsRef.current = items;

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}${path}`)
      .then((r) => r.json())
      .then((data: T[]) => {
        if (!cancelled) {
          setItemsState(data);
          setLoaded(true);
        }
      })
      .catch((e) => {
        console.error(`API GET ${path} failed`, e);
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [path]);

  const setItems: SetList<T> = useCallback(
    (next) => {
      const prev = itemsRef.current;
      const value =
        typeof next === "function" ? (next as (p: T[]) => T[])(prev) : next;
      setItemsState(value); // optimistic
      syncDiff(path, prev, value); // fire-and-forget writes
    },
    [path],
  );

  return [items, setItems, loaded];
}

export function useExperiences() {
  return useApiList<Experience>("/experiences");
}

export function useSessions() {
  return useApiList<Session>("/sessions");
}
