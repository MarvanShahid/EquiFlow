"use client";

/* Shared UI building blocks. Every status uses an icon and a text label, never colour alone. */

import {
  AlertOctagon,
  AlertTriangle,
  CheckCircle2,
  Info,
  Loader2,
  Lock,
  Siren,
  X,
  type LucideIcon,
} from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useId, useRef, useState, type ReactNode } from "react";
import type { Link } from "@/lib/live";
import type { Severity } from "@/lib/events";

/* ------------------------------------------------------------------ layout */
export function PageHeader({ title, description, actions }: { title: string; description?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="page-head">
      <div className="page-head-text">
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  );
}

export function Card({
  title, sub, icon: Icon, actions, children, className = "", flush = false, foot, id, labelledBy,
}: {
  title?: ReactNode;
  sub?: ReactNode;
  icon?: LucideIcon;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
  flush?: boolean;
  foot?: ReactNode;
  id?: string;
  labelledBy?: string;
}) {
  const autoId = useId();
  const hid = title ? `${autoId}-h` : undefined;
  return (
    <section className={`card ${className}`} aria-labelledby={labelledBy ?? hid} id={id}>
      {(title || actions) && (
        <div className="card-head">
          <div className="card-head-text">
            {title && (
              <h3 className="card-title" id={hid}>
                {Icon && <Icon size={16} aria-hidden="true" />}
                {title}
              </h3>
            )}
            {sub && <p className="card-sub">{sub}</p>}
          </div>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      <div className={`card-body${flush ? " flush" : ""}`}>{children}</div>
      {foot && <div className="card-foot">{foot}</div>}
    </section>
  );
}

/* ------------------------------------------------------------------ KPI */
export type Tone = "ok" | "warn" | "crit" | "emg" | "info" | "neutral";

export function Kpi({
  label, value, unit, icon: Icon, meta, tone = "neutral", na,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  icon: LucideIcon;
  meta?: ReactNode;
  tone?: Tone;
  /** shown instead of the value when the data does not exist (e.g. "Not configured") */
  na?: string | null;
}) {
  return (
    <div className={`kpi tone-${tone}`}>
      <div className="kpi-top">
        <span className="kpi-label">{label}</span>
        <span className="kpi-icon" aria-hidden="true">
          <Icon size={16} />
        </span>
      </div>
      {na ? (
        <div className="kpi-value is-na">{na}</div>
      ) : (
        <div className="kpi-value">
          {value}
          {unit && <small>{unit}</small>}
        </div>
      )}
      {meta && <div className="kpi-meta">{meta}</div>}
    </div>
  );
}

/* ------------------------------------------------------------------ badges */
const TONE_ICON: Record<string, LucideIcon> = {
  ok: CheckCircle2,
  warn: AlertTriangle,
  crit: AlertOctagon,
  emg: Siren,
  info: Info,
};

export function Badge({ tone = "neutral", children, icon, dot, pulse, lg, title }: {
  tone?: Tone | "solid-crit" | "solid-emg";
  children: ReactNode;
  icon?: LucideIcon | false;
  dot?: boolean;
  pulse?: boolean;
  lg?: boolean;
  title?: string;
}) {
  const Icon = icon === false ? null : icon ?? (dot ? null : TONE_ICON[tone.replace("solid-", "")]);
  return (
    <span className={`badge ${tone}${lg ? " lg" : ""}`} title={title}>
      {dot && <span className={`dot${pulse ? " pulse" : ""}`} aria-hidden="true" />}
      {Icon && <Icon size={12} aria-hidden="true" />}
      {children}
    </span>
  );
}

export const SEVERITY_TONE: Record<Severity, Tone> = { crit: "crit", warn: "warn", emg: "emg", ok: "ok", info: "info" };

export function LinkBadge({ link, label }: { link: Link; label: string }) {
  const tone = link === "live" ? "ok" : link === "connecting" ? "warn" : "crit";
  const word = link === "live" ? "Connected" : link === "connecting" ? "Connecting" : "Offline";
  return (
    <Badge tone={tone} dot pulse={link === "connecting"} title={`${label}: ${word}`}>
      <span className="badge-label">{label}: </span>
      {word}
    </Badge>
  );
}

/* ------------------------------------------------------------------ empty / banners / messages */
export function Empty({ icon: Icon = Info, title, children, compact, action }: {
  icon?: LucideIcon;
  title: string;
  children?: ReactNode;
  compact?: boolean;
  action?: ReactNode;
}) {
  return (
    <div className={`empty${compact ? " compact" : ""}`} role="status">
      <Icon size={compact ? 22 : 28} aria-hidden="true" />
      <strong>{title}</strong>
      {children && <p>{children}</p>}
      {action}
    </div>
  );
}

export function Banner({ tone, title, children, action, icon }: {
  tone: "crit" | "warn" | "info" | "emg";
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
  icon?: LucideIcon;
}) {
  const Icon = icon ?? TONE_ICON[tone];
  return (
    <div className={`banner ${tone}`} role={tone === "crit" || tone === "emg" ? "alert" : "status"}>
      <Icon size={20} aria-hidden="true" />
      <div className="banner-text">
        <strong>{title}</strong>
        {children && <p>{children}</p>}
      </div>
      {action}
    </div>
  );
}

export function InlineMsg({ tone, children }: { tone: "crit" | "ok" | "info" | "warn"; children: ReactNode }) {
  const Icon = tone === "ok" ? CheckCircle2 : tone === "crit" ? AlertOctagon : tone === "warn" ? AlertTriangle : Info;
  return (
    <p className={`inline-msg ${tone}`} role={tone === "crit" ? "alert" : "status"}>
      <Icon size={14} aria-hidden="true" />
      <span>{children}</span>
    </p>
  );
}

export function Skeleton({ h = 16, w = "100%" }: { h?: number; w?: number | string }) {
  return <div className="skeleton" style={{ height: h, width: w }} aria-hidden="true" />;
}

/* ------------------------------------------------------------------ controls */
export function Segmented<T extends string | number>({ legend, value, options, onChange, disabled }: {
  legend: string;
  value: T | undefined;
  options: { value: T; label: string; title?: string }[];
  onChange: (v: T) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset className="seg">
      <legend>{legend}</legend>
      <div className="seg-btns">
        {options.map((o) => (
          <button key={String(o.value)} type="button" title={o.title} aria-pressed={value === o.value} disabled={disabled} onClick={() => onChange(o.value)}>
            {o.label}
          </button>
        ))}
      </div>
    </fieldset>
  );
}

export function Tabs<T extends string>({ label, value, tabs, onChange }: {
  label: string;
  value: T;
  tabs: { id: T; label: string; icon?: LucideIcon }[];
  onChange: (v: T) => void;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: React.KeyboardEvent, i: number) => {
    const n = tabs.length;
    const j = e.key === "ArrowRight" ? (i + 1) % n : e.key === "ArrowLeft" ? (i - 1 + n) % n : -1;
    if (j >= 0) {
      e.preventDefault();
      onChange(tabs[j].id);
      refs.current[j]?.focus();
    }
  };
  return (
    <div className="tabs" role="tablist" aria-label={label}>
      {tabs.map((t, i) => (
        <button
          key={t.id}
          ref={(el) => {
            refs.current[i] = el;
          }}
          role="tab"
          type="button"
          aria-selected={value === t.id}
          tabIndex={value === t.id ? 0 : -1}
          onClick={() => onChange(t.id)}
          onKeyDown={(e) => onKey(e, i)}
        >
          {t.icon && <t.icon size={15} aria-hidden="true" />}
          {t.label}
        </button>
      ))}
    </div>
  );
}

export function KV({ rows, left }: { rows: [ReactNode, ReactNode][]; left?: boolean }) {
  return (
    <dl className={`kv${left ? " left" : ""}`}>
      {rows.map(([k, v], i) => (
        <div key={i} style={{ display: "contents" }}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Explains why a control is unavailable to the current role. The backend enforces the same rule. */
export function ReadOnlyNote({ children }: { children?: ReactNode }) {
  return (
    <p className="inline-msg info">
      <Lock size={14} aria-hidden="true" />
      <span>{children ?? "Read-only: sign in with an operator key to use these controls."}</span>
    </p>
  );
}

/* ------------------------------------------------------------------ signal lamps */
export function LampStack({ lamp, flashing, small }: { lamp: string | undefined; flashing?: boolean; small?: boolean }) {
  const shown = flashing ? "red" : lamp;
  const size = small ? 12 : 16;
  return (
    <span className="lamp-stack" aria-hidden="true">
      {(["red", "yellow", "green"] as const).map((c) => (
        <span
          key={c}
          className={`lamp ${c}${shown === c ? " on" : ""}${flashing && c === "red" ? " flash" : ""}`}
          style={{ width: size, height: size }}
        />
      ))}
    </span>
  );
}

export function LampWord({ lamp, flashing }: { lamp: string | undefined; flashing?: boolean }) {
  const l = flashing ? "red" : lamp ?? "red";
  return <span className={`lamp-word ${l}`}>{flashing ? "FLASHING RED" : l.toUpperCase()}</span>;
}

export function LampPill({ lamp }: { lamp: string | undefined }) {
  const l = lamp ?? "red";
  return (
    <span className={`lamp-pill ${l}`}>
      <i aria-hidden="true" />
      {l.charAt(0).toUpperCase() + l.slice(1)}
    </span>
  );
}

/* ------------------------------------------------------------------ confirm dialog */
export interface ConfirmOptions {
  title: string;
  body: ReactNode;
  confirmLabel: string;
  tone?: "crit" | "emg" | "warn" | "info";
  /** optional extra content (e.g. a duration picker); read its value from your own state */
  extra?: ReactNode;
}

export function ConfirmDialog({ open, opts, onCancel, onConfirm }: {
  open: boolean;
  opts: ConfirmOptions | null;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const id = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
      cancelRef.current?.focus(); // the safe choice has focus by default
    } else if (!open && d.open) d.close();
  }, [open]);
  const tone = opts?.tone ?? "warn";
  const Icon = tone === "crit" ? AlertOctagon : tone === "emg" ? Siren : tone === "info" ? Info : AlertTriangle;
  return (
    <dialog
      ref={ref}
      className="dialog"
      aria-labelledby={`${id}-t`}
      aria-describedby={`${id}-d`}
      onCancel={(e) => {
        e.preventDefault();
        onCancel();
      }}
    >
      {opts && (
        <>
          <div className="dialog-body">
            <div className="dialog-head">
              <span className={`dialog-icon ${tone}`} aria-hidden="true">
                <Icon size={18} />
              </span>
              <div>
                <h2 id={`${id}-t`}>{opts.title}</h2>
                <div id={`${id}-d`} style={{ marginTop: 6 }}>
                  {typeof opts.body === "string" ? <p>{opts.body}</p> : opts.body}
                </div>
              </div>
            </div>
            {opts.extra}
          </div>
          <div className="dialog-actions">
            <button ref={cancelRef} type="button" className="btn" onClick={onCancel}>
              Cancel
            </button>
            <button type="button" className={`btn ${tone === "crit" ? "danger" : tone === "emg" ? "emg" : "primary"}`} onClick={onConfirm}>
              {opts.confirmLabel}
            </button>
          </div>
        </>
      )}
    </dialog>
  );
}

/** Hook: const { confirm, dialog } = useConfirm(); ... confirm({...}).then(ok => ...) ; render {dialog} */
export function useConfirm() {
  const [state, setState] = useState<{ opts: ConfirmOptions; resolve: (ok: boolean) => void } | null>(null);
  const confirm = useCallback((opts: ConfirmOptions) => new Promise<boolean>((resolve) => setState({ opts, resolve })), []);
  const close = (ok: boolean) => {
    state?.resolve(ok);
    setState(null);
  };
  const dialog = <ConfirmDialog open={!!state} opts={state?.opts ?? null} onCancel={() => close(false)} onConfirm={() => close(true)} />;
  return { confirm, dialog };
}

/* ------------------------------------------------------------------ toasts (operation feedback) */
type ToastTone = "ok" | "crit" | "pending" | "info";
interface ToastItem {
  id: number;
  tone: ToastTone;
  title: string;
  detail?: string;
}
interface ToastApi {
  push: (t: Omit<ToastItem, "id">) => number;
  update: (id: number, t: Omit<ToastItem, "id">) => void;
  dismiss: (id: number) => void;
}
const ToastCtx = createContext<ToastApi | null>(null);
let toastSeq = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const timers = useRef(new Map<number, ReturnType<typeof setTimeout>>());
  const dismiss = useCallback((id: number) => {
    setItems((xs) => xs.filter((x) => x.id !== id));
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
  }, []);
  const schedule = useCallback(
    (id: number, tone: ToastTone) => {
      clearTimeout(timers.current.get(id));
      if (tone === "pending") return;
      timers.current.set(id, setTimeout(() => dismiss(id), tone === "crit" ? 10000 : 5000));
    },
    [dismiss],
  );
  const push = useCallback(
    (t: Omit<ToastItem, "id">) => {
      const id = toastSeq++;
      setItems((xs) => [...xs.slice(-3), { ...t, id }]);
      schedule(id, t.tone);
      return id;
    },
    [schedule],
  );
  const update = useCallback(
    (id: number, t: Omit<ToastItem, "id">) => {
      setItems((xs) => xs.map((x) => (x.id === id ? { ...t, id } : x)));
      schedule(id, t.tone);
    },
    [schedule],
  );
  useEffect(() => {
    const m = timers.current;
    return () => m.forEach((t) => clearTimeout(t));
  }, []);
  const api = useRef<ToastApi>({ push, update, dismiss });
  api.current = { push, update, dismiss };
  const stable = useRef<ToastApi>({
    push: (t) => api.current.push(t),
    update: (i, t) => api.current.update(i, t),
    dismiss: (i) => api.current.dismiss(i),
  });
  return (
    <ToastCtx.Provider value={stable.current}>
      {children}
      <div className="toasts" aria-live="polite" aria-relevant="additions text">
        {items.map((t) => {
          const Icon = t.tone === "ok" ? CheckCircle2 : t.tone === "crit" ? AlertOctagon : t.tone === "pending" ? Loader2 : Info;
          return (
            <div key={t.id} className={`toast ${t.tone}`} role={t.tone === "crit" ? "alert" : "status"}>
              <Icon size={18} aria-hidden="true" />
              <div className="toast-text">
                <strong>{t.title}</strong>
                {t.detail && <span>{t.detail}</span>}
              </div>
              <button type="button" className="btn ghost icon sm" aria-label="Dismiss notification" onClick={() => dismiss(t.id)}>
                <X size={14} aria-hidden="true" />
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

export function useToast(): ToastApi {
  const t = useContext(ToastCtx);
  if (!t) throw new Error("useToast outside ToastProvider");
  return t;
}

/** Runs a backend command with pending / success / failure feedback. Returns true when it succeeded. */
export function useCommand() {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const run = useCallback(
    async (label: string, fn: () => Promise<unknown>, success?: string | ((r: unknown) => string)) => {
      setBusy(true);
      const id = toast.push({ tone: "pending", title: label, detail: "Sending to the backend…" });
      try {
        const r = await fn();
        toast.update(id, { tone: "ok", title: label, detail: typeof success === "function" ? success(r) : success ?? "Accepted by the backend." });
        return true;
      } catch (e) {
        toast.update(id, { tone: "crit", title: `${label}: rejected`, detail: e instanceof Error ? e.message : "Request failed" });
        return false;
      } finally {
        setBusy(false);
      }
    },
    [toast],
  );
  return { run, busy };
}
