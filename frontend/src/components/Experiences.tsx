"use client";

/* Experiences tab (SPEC §5): catalog list + inline add/edit form. */

import { useState } from "react";
import { Clock, Pause, Pencil, Play, Plus, Trash2, Users } from "lucide-react";
import {
  Experience,
  randomId,
  useExperiences,
} from "@/lib/store";

function blankDraft(): Experience {
  return {
    id: randomId("exp"),
    title: "",
    location: "",
    description: "",
    priceAmount: 0,
    priceUnit: "booking",
    capacity: 1,
    durationHours: 2,
    status: "paused",
  };
}

export default function Experiences() {
  const [items, setItems, loaded] = useExperiences();
  const [draft, setDraft] = useState<Experience | null>(null);

  const save = () => {
    if (!draft) return;
    setItems((prev) =>
      prev.some((e) => e.id === draft.id)
        ? prev.map((e) => (e.id === draft.id ? draft : e))
        : [...prev, draft],
    );
    setDraft(null);
  };

  const remove = (id: string) =>
    setItems((prev) => prev.filter((e) => e.id !== id));

  const toggle = (id: string) =>
    setItems((prev) =>
      prev.map((e) =>
        e.id === id
          ? { ...e, status: e.status === "published" ? "paused" : "published" }
          : e,
      ),
    );

  const set = <K extends keyof Experience>(key: K, value: Experience[K]) =>
    setDraft((d) => (d ? { ...d, [key]: value } : d));

  const valid = draft && draft.title.trim() !== "" && draft.priceAmount >= 0;

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <button
          onClick={() => setDraft(blankDraft())}
          className="flex h-8 items-center gap-1.5 rounded-sm bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-walnut"
        >
          <Plus size={14} /> Add experience
        </button>
      </div>

      {draft && (
        <form
          className="mb-6 rounded border border-border p-4"
          onSubmit={(e) => {
            e.preventDefault();
            save();
          }}
        >
          <div className="grid grid-cols-2 gap-4">
            <label className="col-span-2 block">
              <span className="mb-1 block text-sm text-secondary">Title</span>
              <input
                className="input"
                autoFocus
                value={draft.title}
                onChange={(e) => set("title", e.target.value)}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm text-secondary">Location</span>
              <input
                className="input"
                value={draft.location}
                onChange={(e) => set("location", e.target.value)}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm text-secondary">
                Duration (hours)
              </span>
              <input
                className="input"
                type="number"
                min={0}
                step={0.5}
                value={draft.durationHours}
                onChange={(e) => set("durationHours", Number(e.target.value))}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm text-secondary">Price (€)</span>
              <input
                className="input"
                type="number"
                min={0}
                value={draft.priceAmount}
                onChange={(e) => set("priceAmount", Number(e.target.value))}
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-sm text-secondary">Charged</span>
              <select
                className="input"
                value={draft.priceUnit}
                onChange={(e) =>
                  set("priceUnit", e.target.value as Experience["priceUnit"])
                }
              >
                <option value="booking">per booking</option>
                <option value="person">per person</option>
              </select>
            </label>
            <label className="col-span-2 block">
              <span className="mb-1 block text-sm text-secondary">
                Capacity (max people)
              </span>
              <input
                className="input"
                type="number"
                min={1}
                value={draft.capacity}
                onChange={(e) => set("capacity", Number(e.target.value))}
              />
            </label>
            <label className="col-span-2 block">
              <span className="mb-1 block text-sm text-secondary">
                What&apos;s included
              </span>
              <textarea
                className="input min-h-20"
                value={draft.description}
                onChange={(e) => set("description", e.target.value)}
              />
            </label>
          </div>
          <div className="mt-4 flex gap-2">
            <button
              type="submit"
              disabled={!valid}
              className="h-8 rounded-sm bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-walnut disabled:opacity-40"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => setDraft(null)}
              className="h-8 rounded-sm px-3 text-sm hover:bg-accent"
            >
              Cancel
            </button>
          </div>
        </form>
      )}

      {loaded && items.length === 0 && !draft && (
        <p className="py-12 text-center text-muted-foreground">
          No experiences yet.
        </p>
      )}

      <div className="space-y-2">
        {items.map((exp) => (
          <div
            key={exp.id}
            className="group rounded border border-border p-4 transition-colors hover:bg-accent/50"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className={`h-2 w-2 shrink-0 rounded-full ${
                      exp.status === "published"
                        ? "bg-success"
                        : "bg-muted-foreground"
                    }`}
                    title={exp.status === "published" ? "Published" : "Paused"}
                  />
                  <span className="truncate font-medium">{exp.title}</span>
                </div>
                {exp.location && (
                  <div className="pl-4 text-sm text-muted-foreground">
                    {exp.location}
                  </div>
                )}
              </div>
              <div className="shrink-0 text-right">
                <div>
                  <span className="font-medium">€{exp.priceAmount}</span>{" "}
                  <span className="text-xs text-muted-foreground">
                    / {exp.priceUnit}
                  </span>
                </div>
                <div className="mt-1 flex items-center justify-end gap-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Users size={12} /> {exp.capacity}
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock size={12} /> {exp.durationHours}h
                  </span>
                </div>
              </div>
            </div>

            {exp.description && (
              <p className="mt-2 pl-4 text-sm text-secondary">
                {exp.description}
              </p>
            )}

            <div className="mt-2 flex justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
              <button
                onClick={() => toggle(exp.id)}
                className="rounded-sm p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                title={exp.status === "published" ? "Pause" : "Publish"}
              >
                {exp.status === "published" ? (
                  <Pause size={14} />
                ) : (
                  <Play size={14} />
                )}
              </button>
              <button
                onClick={() => setDraft(exp)}
                className="rounded-sm p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
                title="Edit"
              >
                <Pencil size={14} />
              </button>
              <button
                onClick={() => remove(exp.id)}
                className="rounded-sm p-1.5 text-muted-foreground hover:bg-accent hover:text-destructive"
                title="Delete"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
