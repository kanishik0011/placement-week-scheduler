"use client";

import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Building2,
  CheckCircle2,
  Clock,
  DoorOpen,
  Play,
  RefreshCcw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Users,
  Wrench
} from "lucide-react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, minuteLabel } from "./api";
import type { Company, DatasetSummary, Interview, Metrics, Replan, Room, Student } from "./types";

type Mode = "operations" | "defense";

function cx(...items: Array<string | false | undefined>) {
  return items.filter(Boolean).join(" ");
}

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cx("rounded-md border border-line bg-white p-4 shadow-sm", className)}>{children}</section>;
}

function Button({ children, onClick, disabled, intent = "primary" }: { children: React.ReactNode; onClick: () => void; disabled?: boolean; intent?: "primary" | "quiet" | "danger" }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={cx(
        "inline-flex h-10 items-center gap-2 rounded-md border px-3 text-sm font-semibold",
        intent === "primary" && "border-ink bg-ink text-white",
        intent === "quiet" && "border-line bg-white text-ink",
        intent === "danger" && "border-danger bg-danger text-white"
      )}
    >
      {children}
    </button>
  );
}

function Stat({ icon: Icon, label, value, tone }: { icon: typeof CheckCircle2; label: string; value: string | number; tone?: "ok" | "warn" | "danger" }) {
  return (
    <Card>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</div>
          <div className="mt-2 text-2xl font-bold">{value}</div>
        </div>
        <Icon className={cx("h-6 w-6", tone === "ok" && "text-ok", tone === "warn" && "text-warn", tone === "danger" && "text-danger", !tone && "text-slate-500")} />
      </div>
    </Card>
  );
}

function useOps() {
  const qc = useQueryClient();
  const invalidate = () => Promise.all(["summary", "metrics", "schedule", "companies", "students", "rooms", "events"].map((key) => qc.invalidateQueries({ queryKey: [key] })));
  return {
    generate: useApiMutation<{ seed: number }, unknown>("/dataset/generate", invalidate),
    schedule: useApiMutation<Record<string, never>, unknown>("/schedule/generate", invalidate),
    replan: useApiMutation<Record<string, never>, Replan>("/replan", invalidate),
    validate: useApiMutation<Record<string, never>, unknown>("/schedule/validate", invalidate),
    clock: useApiMutation<{ day: number; hour: number; minute: number }, unknown>("/clock", invalidate),
    crisis: useApiMutation<Record<string, never>, unknown>("/disruptions/day1-crisis", invalidate),
    companyDelay: useApiMutation<{ company_id: string; delay_minutes: number }, unknown>("/disruptions/company-delay", invalidate),
    panelDrop: useApiMutation<{ panel_id: string }, unknown>("/disruptions/panel-drop", invalidate),
    studentWithdrawal: useApiMutation<{ student_id: string; reason: string }, unknown>("/disruptions/student-withdrawal", invalidate),
    roomUnavailable: useApiMutation<{ room_id: string; day: number; start_hour: number; end_hour: number }, unknown>("/disruptions/room-unavailable", invalidate)
  };
}

function useApiMutation<TBody, TResult>(path: string, onSuccess: () => Promise<unknown>) {
  return useMutation({
    mutationFn: (body: TBody) => api<TResult>(path, { method: "POST", body: JSON.stringify(body ?? {}) }),
    onSuccess
  });
}

export function Dashboard({ mode }: { mode: Mode }) {
  const [tab, setTab] = useState(mode === "defense" ? "defense" : "overview");
  const [search, setSearch] = useState("");
  const [lastReplan, setLastReplan] = useState<Replan | null>(null);
  const ops = useOps();
  const busy = Object.values(ops).some((m) => m.isPending);
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => api<DatasetSummary>("/dataset/summary") });
  const metrics = useQuery({ queryKey: ["metrics"], queryFn: () => api<Metrics>("/schedule/metrics") });
  const interviews = useQuery({ queryKey: ["schedule"], queryFn: () => api<Interview[]>("/schedule") });
  const companies = useQuery({ queryKey: ["companies"], queryFn: () => api<Company[]>("/companies") });
  const students = useQuery({ queryKey: ["students"], queryFn: () => api<Student[]>("/students") });
  const rooms = useQuery({ queryKey: ["rooms"], queryFn: () => api<Room[]>("/rooms") });
  const events = useQuery({ queryKey: ["events"], queryFn: () => api<Array<{ id: string; description: string; event_type: string }>>("/events") });

  const dataReady = summary.data && metrics.data && interviews.data && companies.data && students.data && rooms.data;
  const companyById = useMemo(() => new Map((companies.data ?? []).map((c) => [c.id, c])), [companies.data]);
  const studentById = useMemo(() => new Map((students.data ?? []).map((s) => [s.id, s])), [students.data]);
  const scheduled = (interviews.data ?? []).filter((i) => i.status === "scheduled");
  const unresolved = (interviews.data ?? []).filter((i) => i.status === "unscheduled");
  const activeCompanies = new Set(scheduled.map((i) => i.company_id)).size;
  const visibleStudents = (students.data ?? []).filter((s) => `${s.name} ${s.roll_number} ${s.branch}`.toLowerCase().includes(search.toLowerCase())).slice(0, 80);
  const visibleInterviews = scheduled.slice(0, 160);
  const chart = Object.entries(metrics.data?.unscheduled_by_reason ?? {}).map(([name, value]) => ({ name, value }));

  const runReplan = () => ops.replan.mutate({}, { onSuccess: (r) => setLastReplan(r) });

  return (
    <main className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-[1500px] items-center justify-between px-5 py-4">
          <div>
            <h1 className="text-xl font-bold">Placement Week Scheduler</h1>
            <p className="text-sm text-slate-600">Minimal-disruption command center for live placement operations</p>
          </div>
          <div className="flex gap-2">
            <Button intent="quiet" disabled={busy} onClick={() => ops.generate.mutate({ seed: 42 })}>
              <RefreshCcw className="h-4 w-4" /> Demo Reset
            </Button>
            <Button disabled={busy} onClick={() => ops.schedule.mutate({})}>
              <Play className="h-4 w-4" /> Build Schedule
            </Button>
            <Button disabled={busy} onClick={runReplan}>
              <Wrench className="h-4 w-4" /> Replan
            </Button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-[1500px] grid-cols-[220px_1fr] gap-5 px-5 py-5">
        <nav className="space-y-2">
          {["overview", "timeline", "rooms", "companies", "students", "unscheduled", "disruptions", "replan", "defense"].map((item) => (
            <button key={item} onClick={() => setTab(item)} className={cx("flex w-full items-center rounded-md px-3 py-2 text-left text-sm font-semibold capitalize", tab === item ? "bg-ink text-white" : "bg-white text-slate-700")}>
              {item}
            </button>
          ))}
        </nav>

        <div className="space-y-5">
          {!dataReady && <Card>Loading API state. Start the FastAPI server if this persists.</Card>}
          {metrics.error && <Card className="border-danger text-danger">{String(metrics.error.message)}</Card>}

          {dataReady && (
            <>
              {(tab === "overview" || tab === "defense") && (
                <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-4 xl:grid-cols-6">
                    <Stat icon={Clock} label="Simulated Time" value={minuteLabel(summary.data.current_time)} />
                    <Stat icon={ShieldCheck} label="Validation" value={metrics.data.validation.valid ? "Valid" : `${metrics.data.validation.violation_count} issues`} tone={metrics.data.validation.valid ? "ok" : "danger"} />
                    <Stat icon={CheckCircle2} label="Coverage" value={`${Math.round(metrics.data.coverage * 100)}%`} tone={metrics.data.coverage > 0.7 ? "ok" : "warn"} />
                    <Stat icon={Building2} label="Active Companies" value={activeCompanies} />
                    <Stat icon={DoorOpen} label="Rooms" value={summary.data.rooms} />
                    <Stat icon={AlertTriangle} label="Unresolved" value={metrics.data.unscheduled_interviews} tone={metrics.data.unscheduled_interviews ? "warn" : "ok"} />
                  </div>
                  <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
                    <Card>
                      <h2 className="font-bold">Command Center</h2>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <Button intent="quiet" disabled={busy} onClick={() => ops.clock.mutate({ day: 1, hour: 10, minute: 30 })}><Clock className="h-4 w-4" /> Set D1 10:30</Button>
                        <Button intent="quiet" disabled={busy} onClick={() => ops.validate.mutate({})}><ShieldCheck className="h-4 w-4" /> Validate Schedule</Button>
                        <Button intent="danger" disabled={busy} onClick={() => ops.crisis.mutate({})}><AlertTriangle className="h-4 w-4" /> Day-1 Crisis</Button>
                      </div>
                      <p className="mt-4 rounded-md border border-line bg-surface p-3 text-sm text-slate-700">
                        Hard constraints are enforced automatically. Priority-based displacement is suggested by the system and surfaced for coordinator review.
                      </p>
                    </Card>
                    <Card>
                      <h2 className="font-bold">Unscheduled Breakdown</h2>
                      <div className="mt-3 h-52">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={chart}>
                            <XAxis dataKey="name" hide />
                            <YAxis />
                            <Tooltip />
                            <Bar dataKey="value" fill="#2563eb" />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </Card>
                  </div>
                </div>
              )}

              {tab === "timeline" && (
                <Card>
                  <div className="flex items-center justify-between">
                    <h2 className="font-bold">Timeline</h2>
                    <div className="flex items-center gap-2 text-sm text-slate-600"><SlidersHorizontal className="h-4 w-4" /> Showing first 160 scheduled appointments</div>
                  </div>
                  <div className="timeline-grid mt-4 min-w-[900px] space-y-1 overflow-x-auto">
                    {visibleInterviews.map((i) => (
                      <div key={i.id} className="grid grid-cols-[120px_1fr_80px_90px] items-center gap-2 border-b border-slate-100 py-2 text-sm">
                        <span className="font-semibold">{minuteLabel(i.scheduled_start)}</span>
                        <span>{studentById.get(i.student_id)?.name} with {companyById.get(i.company_id)?.name}</span>
                        <span>{i.panel_id}</span>
                        <span>{i.room_id}</span>
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {tab === "rooms" && (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                  {rooms.data.map((room) => {
                    const current = scheduled.find((i) => i.room_id === room.id && i.scheduled_start! <= summary.data.current_time && i.scheduled_end! > summary.data.current_time);
                    const next = scheduled.find((i) => i.room_id === room.id && i.scheduled_start! > summary.data.current_time);
                    return (
                      <Card key={room.id}>
                        <div className="flex items-center justify-between"><h3 className="font-bold">{room.name}</h3><DoorOpen className="h-5 w-5 text-slate-500" /></div>
                        <p className="text-sm text-slate-600">{room.building}, floor {room.floor}</p>
                        <p className="mt-3 text-sm">Now: {current ? companyById.get(current.company_id)?.name : "Free"}</p>
                        <p className="text-sm">Next: {next ? `${minuteLabel(next.scheduled_start)} ${companyById.get(next.company_id)?.name}` : "None"}</p>
                        {room.outage_windows.length > 0 && <p className="mt-2 text-sm font-semibold text-danger">Unavailable window active</p>}
                      </Card>
                    );
                  })}
                </div>
              )}

              {tab === "companies" && (
                <Card>
                  <h2 className="font-bold">Companies</h2>
                  <table className="mt-4 w-full text-left text-sm">
                    <thead><tr className="border-b"><th>Name</th><th>Tier</th><th>Type</th><th>Panels</th><th>Scheduled</th><th>Unresolved</th><th>Status</th></tr></thead>
                    <tbody>{companies.data.map((c) => <tr key={c.id} className="border-b border-slate-100"><td className="py-2 font-semibold">{c.name}</td><td>{c.priority_tier}</td><td>{c.company_type}</td><td>{c.panel_count}</td><td>{scheduled.filter((i) => i.company_id === c.id).length}</td><td>{unresolved.filter((i) => i.company_id === c.id).length}</td><td>{c.status}</td></tr>)}</tbody>
                  </table>
                </Card>
              )}

              {tab === "students" && (
                <Card>
                  <div className="flex items-center gap-2"><Search className="h-4 w-4" /><input className="h-10 flex-1 rounded-md border border-line px-3" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search students" /></div>
                  <table className="mt-4 w-full text-left text-sm">
                    <thead><tr className="border-b"><th>Name</th><th>Roll</th><th>Branch</th><th>CGPA</th><th>Shortlists</th><th>Status</th></tr></thead>
                    <tbody>{visibleStudents.map((s) => <tr key={s.id} className="border-b border-slate-100"><td className="py-2 font-semibold">{s.name}</td><td>{s.roll_number}</td><td>{s.branch}</td><td>{s.cgpa}</td><td>{s.shortlisted_company_ids.length}</td><td>{s.withdrawn ? "withdrawn" : s.placement_status}</td></tr>)}</tbody>
                  </table>
                </Card>
              )}

              {tab === "unscheduled" && (
                <Card>
                  <h2 className="font-bold">Conflicts / Unscheduled</h2>
                  <table className="mt-4 w-full text-left text-sm">
                    <thead><tr className="border-b"><th>Student</th><th>Company</th><th>Priority</th><th>Reason</th><th>Suggested Action</th></tr></thead>
                    <tbody>{unresolved.slice(0, 300).map((i) => <tr key={i.id} className="border-b border-slate-100"><td className="py-2">{studentById.get(i.student_id)?.name}</td><td>{companyById.get(i.company_id)?.name}</td><td>{i.priority}</td><td>{i.unscheduled_reason_code}</td><td className="max-w-xl">{i.unscheduled_reason}</td></tr>)}</tbody>
                  </table>
                </Card>
              )}

              {tab === "disruptions" && (
                <div className="grid gap-5 xl:grid-cols-2">
                  <Card><h2 className="font-bold">Company Late</h2><Button disabled={busy || !companies.data[0]} onClick={() => ops.companyDelay.mutate({ company_id: companies.data[0].id, delay_minutes: 180 })}><AlertTriangle className="h-4 w-4" /> Delay First Company 3h</Button></Card>
                  <Card><h2 className="font-bold">Panel Dropped</h2><Button disabled={busy || !scheduled[0]?.panel_id} onClick={() => ops.panelDrop.mutate({ panel_id: scheduled[0].panel_id! })}><Wrench className="h-4 w-4" /> Drop Active Panel</Button></Card>
                  <Card><h2 className="font-bold">Student Withdrawn</h2><Button disabled={busy || !scheduled[0]} onClick={() => ops.studentWithdrawal.mutate({ student_id: scheduled[0].student_id, reason: "Coordinator demo withdrawal" })}><Users className="h-4 w-4" /> Withdraw Scheduled Student</Button></Card>
                  <Card><h2 className="font-bold">Room Unavailable</h2><Button disabled={busy || !scheduled[0]?.room_id} onClick={() => ops.roomUnavailable.mutate({ room_id: scheduled[0].room_id!, day: 1, start_hour: 11, end_hour: 13 })}><DoorOpen className="h-4 w-4" /> Block Room</Button></Card>
                </div>
              )}

              {tab === "replan" && (
                <Card>
                  <h2 className="font-bold">Replan Change Summary</h2>
                  {!lastReplan && <p className="mt-3 text-sm text-slate-600">Run Replan to see a before/after diff.</p>}
                  {lastReplan && (
                    <>
                      <div className="mt-3 rounded-md border border-line bg-surface p-3 text-sm text-slate-700">
                        <span className="font-semibold text-ink">Disruption:</span> {String(lastReplan.summary.disruption_description)}
                      </div>
                      <div className="mt-3 grid grid-cols-2 gap-3 xl:grid-cols-5">
                        <div className="rounded-md border border-line p-3">
                          <div className="text-xs uppercase text-slate-500">Validation</div>
                          <div className={cx("font-bold", lastReplan.validation.valid ? "text-ok" : "text-danger")}>{lastReplan.validation.valid ? "Valid" : `${lastReplan.validation.violation_count} issues`}</div>
                        </div>
                        {Object.entries(lastReplan.summary)
                          .filter(([k]) => k !== "disruption_description")
                          .slice(0, 10)
                          .map(([k, v]) => (
                            <div key={k} className="rounded-md border border-line p-3">
                              <div className="text-xs uppercase text-slate-500">{k.replaceAll("_", " ")}</div>
                              <div className="font-bold">{String(v)}</div>
                            </div>
                          ))}
                      </div>
                      <table className="mt-4 w-full text-left text-sm"><thead><tr className="border-b"><th>Change</th><th>Interview</th><th>Old</th><th>New</th><th>Shift</th></tr></thead><tbody>{lastReplan.changes.filter((c) => c.classification !== "unchanged").slice(0, 120).map((c) => <tr key={String(c.interview_id)} className="border-b border-slate-100"><td className="py-2 font-semibold">{String(c.classification)}</td><td>{String(c.interview_id)}</td><td>{String(c.old_start ?? "-")} {String(c.old_room ?? "")}</td><td>{String(c.new_start ?? "-")} {String(c.new_room ?? "")}</td><td>{String(c.shift_minutes)}</td></tr>)}</tbody></table>
                    </>
                  )}
                </Card>
              )}

              {tab === "defense" && (
                <Card>
                  <h2 className="font-bold">Defense Mode</h2>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Button intent="quiet" disabled={busy} onClick={() => ops.generate.mutate({ seed: 42 })}>1. Reset Dataset</Button>
                    <Button intent="quiet" disabled={busy} onClick={() => ops.schedule.mutate({})}>2. Initial Schedule</Button>
                    <Button intent="quiet" disabled={busy} onClick={() => ops.clock.mutate({ day: 1, hour: 10, minute: 30 })}>3. Set Clock</Button>
                    <Button intent="danger" disabled={busy} onClick={() => ops.crisis.mutate({})}>4. Day-1 Crisis</Button>
                    <Button disabled={busy} onClick={runReplan}>5. Run Replan</Button>
                  </div>
                  <div className="mt-4 text-sm text-slate-700">Execution status, validator state, coverage, churn, and unresolved interviews update from the backend after each step.</div>
                </Card>
              )}

              <Card>
                <h2 className="font-bold">Recent Activity</h2>
                <div className="mt-3 space-y-2 text-sm">{(events.data ?? []).slice().reverse().slice(0, 8).map((event) => <div key={event.id} className="rounded-md bg-surface p-2"><span className="font-semibold">{event.event_type}</span> {event.description}</div>)}</div>
              </Card>
            </>
          )}
        </div>
      </div>
    </main>
  );
}
