"use client";

import { Download, RefreshCw, ScrollText, Search } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { getEvents } from "@/lib/api";
import { CATEGORY_LABEL, SEVERITY_LABEL, toFeed, type Category, type Severity } from "@/lib/events";
import { dateTime } from "@/lib/format";
import { useLive } from "@/lib/live";
import type { EquiEvent } from "@/lib/types";
import { Badge, Card, Empty, PageHeader, SEVERITY_TONE } from "../ui";

const PAGE = 100;

export default function Logs() {
  const live = useLive((s) => s.eq.events);
  const sumo = useLive((s) => s.sumo.events);
  const mode = useLive((s) => s.eq.snapshot?.mode);
  const [fetched, setFetched] = useState<EquiEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sev, setSev] = useState<Severity | "all">("all");
  const [cat, setCat] = useState<Category | "all">("all");
  const [origin, setOrigin] = useState<"all" | "junction" | "simulation">("all");
  const [q, setQ] = useState("");
  const [shown, setShown] = useState(PAGE);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setFetched(await getEvents(500));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  const all = useMemo(() => {
    const byId = new Map<number, EquiEvent>();
    for (const e of [...fetched, ...live]) byId.set(e.id, e);
    return toFeed([...byId.values()], sumo, mode);
  }, [fetched, live, sumo, mode]);

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return all.filter(
      (f) =>
        (sev === "all" || f.d.severity === sev) &&
        (cat === "all" || f.d.category === cat) &&
        (origin === "all" || f.origin === origin) &&
        (!needle || f.d.text.toLowerCase().includes(needle) || f.type.includes(needle)),
    );
  }, [all, sev, cat, origin, q]);

  useEffect(() => setShown(PAGE), [sev, cat, origin, q]);

  const exportCsv = () => {
    const esc = (v: string) => `"${v.replace(/"/g, '""')}"`;
    const lines = ["time,severity,category,source,type,message", ...rows.map((f) => [new Date(f.ts * 1000).toISOString(), f.d.severity, f.d.category, f.origin, f.type, f.d.text].map(String).map(esc).join(","))];
    const url = URL.createObjectURL(new Blob([lines.join("\n")], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `equiflow-events-${new Date().toISOString().slice(0, 19).replace(/:/g, "")}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="page">
      <PageHeader
        title="System logs"
        description="Events from the backend's event bus (signal changes, detections, priority, safety faults, operator writes, failed sign-ins) and from the SUMO simulation. The backend also writes a CSV event log per run in backend/logs/."
        actions={
          <>
            <button type="button" className="btn sm" onClick={load} disabled={loading}>
              <RefreshCw size={14} aria-hidden="true" className={loading ? "spin" : undefined} /> Refresh
            </button>
            <button type="button" className="btn sm" onClick={exportCsv} disabled={!rows.length}>
              <Download size={14} aria-hidden="true" /> Export CSV
            </button>
          </>
        }
      />
      <Card>
        <div className="toolbar" role="search" aria-label="Filter events">
          <label className="field" style={{ flex: "1 1 240px" }}>
            <span>Search</span>
            <div style={{ position: "relative" }}>
              <Search size={15} aria-hidden="true" style={{ position: "absolute", left: 10, top: 10, color: "var(--text-subtle)" }} />
              <input className="input" style={{ paddingLeft: 32 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Approach, event type, client…" />
            </div>
          </label>
          <label className="field">
            <span>Severity</span>
            <select className="select" value={sev} onChange={(e) => setSev(e.target.value as Severity | "all")}>
              <option value="all">All severities</option>
              {(Object.keys(SEVERITY_LABEL) as Severity[]).map((s) => (
                <option key={s} value={s}>
                  {SEVERITY_LABEL[s]}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Category</span>
            <select className="select" value={cat} onChange={(e) => setCat(e.target.value as Category | "all")}>
              <option value="all">All categories</option>
              {(Object.keys(CATEGORY_LABEL) as Category[]).map((c) => (
                <option key={c} value={c}>
                  {CATEGORY_LABEL[c]}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Source</span>
            <select className="select" value={origin} onChange={(e) => setOrigin(e.target.value as typeof origin)}>
              <option value="all">All sources</option>
              <option value="junction">Camera junction</option>
              <option value="simulation">Simulation</option>
            </select>
          </label>
        </div>
      </Card>

      <Card title="Events" icon={ScrollText} sub={`${rows.length} of ${all.length} events, newest first`} flush>
        {error && <p className="error" style={{ padding: "0 16px 12px" }}>Could not load the backend's event history: {error}. Showing events received live.</p>}
        {rows.length === 0 ? (
          <Empty compact title={all.length ? "No events match the filters" : "No events yet"} />
        ) : (
          <>
            <div className="table-wrap" style={{ maxHeight: "65vh" }}>
              <table className="table">
                <caption className="sr-only">Event log</caption>
                <thead>
                  <tr>
                    <th scope="col">Time</th>
                    <th scope="col">Severity</th>
                    <th scope="col">Category</th>
                    <th scope="col">Source</th>
                    <th scope="col">Event</th>
                    <th scope="col">Type</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, shown).map((f) => (
                    <tr key={f.key} className={f.d.severity === "crit" ? "is-crit" : f.d.severity === "emg" ? "is-emg" : undefined}>
                      <td className="num" style={{ whiteSpace: "nowrap" }}>{dateTime(f.ts)}</td>
                      <td>
                        <Badge tone={SEVERITY_TONE[f.d.severity]}>{SEVERITY_LABEL[f.d.severity]}</Badge>
                      </td>
                      <td>{CATEGORY_LABEL[f.d.category]}</td>
                      <td>{f.origin === "simulation" ? "Simulation" : "Camera junction"}</td>
                      <td style={{ minWidth: 280 }}>{f.d.text}</td>
                      <td className="mono subtle" style={{ fontSize: 12 }}>{f.type}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {shown < rows.length && (
              <div style={{ padding: 12, textAlign: "center" }}>
                <button type="button" className="btn sm" onClick={() => setShown((n) => n + PAGE)}>
                  Show {Math.min(PAGE, rows.length - shown)} more
                </button>
              </div>
            )}
          </>
        )}
      </Card>
      <p className="chart-note">The backend keeps its most recent events in memory; simulation events are those received since this tab opened.</p>
    </div>
  );
}
