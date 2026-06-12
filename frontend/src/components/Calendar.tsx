"use client";

/* Calendar tab (SPEC §7): Monday-start month view of sessions, with an
 * anchored create/edit popup. Pills are colored per-experience (§7f):
 * solid = booked, dashed ghost = open. */

import {
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  addMonths,
  eachDayOfInterval,
  endOfMonth,
  endOfWeek,
  format,
  isBefore,
  isSameMonth,
  isToday,
  startOfDay,
  startOfMonth,
  startOfWeek,
  subMonths,
} from "date-fns";
import { ChevronLeft, ChevronRight, Plus, Trash2, X } from "lucide-react";
import {
  Experience,
  Session,
  randomId,
  useExperiences,
  useSessions,
} from "@/lib/store";
import { NEUTRAL_COLOR, getExperienceColor } from "@/lib/calendar-colors";

type Anchor = { x: number; y: number };
type Popup =
  | { mode: "create"; date: string; anchor: Anchor }
  | { mode: "edit"; session: Session; anchor: Anchor };

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export default function Calendar() {
  const [month, setMonth] = useState(() => startOfDay(new Date()));
  const [sessions, setSessions] = useSessions();
  const [experiences] = useExperiences();
  const [popup, setPopup] = useState<Popup | null>(null);

  const days = useMemo(() => {
    const start = startOfWeek(startOfMonth(month), { weekStartsOn: 1 });
    const end = endOfWeek(endOfMonth(month), { weekStartsOn: 1 });
    return eachDayOfInterval({ start, end });
  }, [month]);

  const byDay = useMemo(() => {
    const map = new Map<string, Session[]>();
    for (const s of sessions) {
      const list = map.get(s.date) ?? [];
      list.push(s);
      map.set(s.date, list);
    }
    for (const list of map.values())
      list.sort((a, b) => a.time.localeCompare(b.time));
    return map;
  }, [sessions]);

  const expById = useMemo(
    () => new Map(experiences.map((e) => [e.id, e])),
    [experiences],
  );

  const today = startOfDay(new Date());

  const upsert = (ses: Session) => {
    setSessions((prev) =>
      prev.some((s) => s.id === ses.id)
        ? prev.map((s) => (s.id === ses.id ? ses : s))
        : [...prev, ses],
    );
    setPopup(null);
  };

  const remove = (id: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== id));
    setPopup(null);
  };

  return (
    <div className="rounded border border-border p-4">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-normal">{format(month, "MMMM yyyy")}</h2>
        <div className="flex items-center gap-1">
          <button
            onClick={() => setMonth((m) => subMonths(m, 1))}
            className="rounded-sm p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            title="Previous month"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            onClick={() => setMonth(startOfDay(new Date()))}
            className="rounded-sm px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            Today
          </button>
          <button
            onClick={() => setMonth((m) => addMonths(m, 1))}
            className="rounded-sm p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
            title="Next month"
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-7">
        {WEEKDAYS.map((d) => (
          <div
            key={d}
            className="pb-2 text-center text-[11px] uppercase tracking-wider text-muted-foreground"
          >
            {d}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-px bg-border">
        {days.map((day) => {
          const key = format(day, "yyyy-MM-dd");
          const daySessions = byDay.get(key) ?? [];
          const past = isBefore(day, today);
          const outside = !isSameMonth(day, month);
          return (
            <div
              key={key}
              onClick={(e) =>
                setPopup({
                  mode: "create",
                  date: key,
                  anchor: { x: e.clientX, y: e.clientY },
                })
              }
              className={`group min-h-[104px] cursor-pointer bg-background px-1 pb-1.5 pt-1 transition-colors hover:bg-accent/40 ${
                outside ? "opacity-30" : past ? "opacity-50" : ""
              }`}
            >
              <div className="mb-1 flex items-start justify-between">
                {isToday(day) ? (
                  <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary text-xs text-primary-foreground">
                    {format(day, "d")}
                  </span>
                ) : (
                  <span className="px-1.5 py-0.5 text-xs text-foreground/80">
                    {format(day, "d")}
                  </span>
                )}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setPopup({
                      mode: "create",
                      date: key,
                      anchor: { x: e.clientX, y: e.clientY },
                    });
                  }}
                  className="rounded-sm p-1 text-muted-foreground opacity-0 transition-opacity hover:bg-accent hover:text-foreground group-hover:opacity-100"
                  title="Add session"
                >
                  <Plus size={12} />
                </button>
              </div>

              <div className="space-y-0.5">
                {daySessions.slice(0, 3).map((s) => (
                  <SessionPill
                    key={s.id}
                    session={s}
                    experience={expById.get(s.experienceId)}
                    onClick={(e) => {
                      e.stopPropagation();
                      setPopup({
                        mode: "edit",
                        session: s,
                        anchor: { x: e.clientX, y: e.clientY },
                      });
                    }}
                  />
                ))}
                {daySessions.length > 3 && (
                  <div className="px-1 text-[11px] text-muted-foreground">
                    +{daySessions.length - 3} more
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {popup && (
        <SessionPopup
          popup={popup}
          experiences={experiences}
          onClose={() => setPopup(null)}
          onSave={upsert}
          onDelete={remove}
        />
      )}
    </div>
  );
}

function SessionPill({
  session,
  experience,
  onClick,
}: {
  session: Session;
  experience: Experience | undefined;
  onClick: (e: React.MouseEvent) => void;
}) {
  const color = experience
    ? getExperienceColor(experience.id)
    : NEUTRAL_COLOR;
  const booked = session.status === "booked";
  return (
    <button
      onClick={onClick}
      className="block w-full truncate rounded-sm px-1.5 py-0.5 text-left text-[11px] transition-[filter] hover:brightness-95"
      style={{
        backgroundColor: booked ? color.bgSolid : color.bgGhost,
        color: booked ? color.textSolid : color.textGhost,
        borderLeft: `3px ${booked ? "solid" : "dashed"} ${color.border}`,
        fontWeight: booked ? 500 : 400,
      }}
    >
      <span className="tabular-nums">{session.time}</span>
      <span className="opacity-70"> · {experience?.title ?? "Unknown"}</span>
    </button>
  );
}

function SessionPopup({
  popup,
  experiences,
  onClose,
  onSave,
  onDelete,
}: {
  popup: Popup;
  experiences: Experience[];
  onClose: () => void;
  onSave: (s: Session) => void;
  onDelete: (id: string) => void;
}) {
  const editing = popup.mode === "edit" ? popup.session : null;
  const [experienceId, setExperienceId] = useState(
    editing?.experienceId ?? experiences[0]?.id ?? "",
  );
  const [date, setDate] = useState(editing?.date ?? (popup.mode === "create" ? popup.date : ""));
  const [time, setTime] = useState(editing?.time ?? "17:00");
  const [status, setStatus] = useState<Session["status"]>(
    editing?.status ?? "open",
  );

  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const { width, height } = el.getBoundingClientRect();
    let left = popup.anchor.x + 8;
    let top = popup.anchor.y + 8;
    if (left + width > window.innerWidth - 16)
      left = window.innerWidth - width - 16;
    if (top + height > window.innerHeight - 16)
      top = window.innerHeight - height - 16;
    setPos({ left: Math.max(16, left), top: Math.max(16, top) });
  }, [popup.anchor.x, popup.anchor.y]);

  const valid = experienceId && date && time;

  const save = () =>
    onSave({
      id: editing?.id ?? randomId("s"),
      experienceId,
      date,
      time,
      status,
    });

  return (
    <>
      <div className="fixed inset-0 z-40" onClick={onClose} />
      <div
        ref={ref}
        onClick={(e) => e.stopPropagation()}
        className="fixed z-50 w-64 rounded-lg border border-border bg-background p-3 shadow-lg"
        style={pos ? { ...pos, opacity: 1 } : { left: 0, top: 0, opacity: 0 }}
      >
        <div className="mb-3 flex items-center justify-between">
          <span className="text-sm font-medium">
            {editing ? "Edit session" : "New session"}
          </span>
          <button
            onClick={onClose}
            className="rounded-sm p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <X size={14} />
          </button>
        </div>

        <div className="space-y-2">
          <select
            className="input"
            value={experienceId}
            onChange={(e) => setExperienceId(e.target.value)}
          >
            {experiences.length === 0 ? (
              <option value="" disabled>
                No experiences
              </option>
            ) : (
              experiences.map((e) => (
                <option key={e.id} value={e.id}>
                  {e.title}
                </option>
              ))
            )}
          </select>

          <div className="flex gap-2">
            <input
              type="date"
              className="input flex-1"
              value={date}
              onChange={(e) => setDate(e.target.value)}
            />
            <input
              type="time"
              className="input w-24"
              value={time}
              onChange={(e) => setTime(e.target.value)}
            />
          </div>

          <div className="flex gap-1">
            {(["open", "booked"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className={`flex-1 rounded-sm px-2 py-1 text-sm capitalize transition-colors ${
                  status === s
                    ? "bg-primary/10 text-primary"
                    : "bg-[rgba(242,241,238,0.6)] text-muted-foreground"
                }`}
              >
                {s}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-1 pt-1">
            <button
              onClick={save}
              disabled={!valid}
              className="h-8 flex-1 rounded-sm bg-primary px-3 text-sm font-medium text-primary-foreground hover:bg-walnut disabled:opacity-40"
            >
              {editing ? "Save" : "Create"}
            </button>
            {editing && (
              <button
                onClick={() => onDelete(editing.id)}
                className="rounded-sm p-1.5 text-muted-foreground hover:bg-accent hover:text-destructive"
                title="Delete session"
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
