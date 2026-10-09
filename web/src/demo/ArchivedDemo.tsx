import { useEffect, useState } from "react";
import { Activity, BookOpen, CheckCircle2, Clapperboard, LayoutDashboard, ScanLine, ShieldCheck, Sparkles } from "lucide-react";
import { SkillReview } from "../components/SkillReview";
import { ErrorNotice, JsonView, Loading, Panel, timeLabel } from "../components/ui";
import { archiveSchema, type Archive } from "./archive";

const pages = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "demonstration", label: "Demonstration", icon: Clapperboard },
  { id: "skill", label: "AI Skill", icon: Sparkles },
  { id: "review", label: "Human Review", icon: ShieldCheck },
  { id: "replay", label: "Replay & Result", icon: Activity },
  { id: "limitations", label: "Limitations", icon: BookOpen },
] as const;
type Page = typeof pages[number]["id"];
function initialPage(): Page {
  const hash = window.location.hash.slice(1);
  return pages.find(page => page.id === hash)?.id ?? "overview";
}

export default function ArchivedDemo() {
  const [page, setPage] = useState<Page>(initialPage);
  const [archive, setArchive] = useState<Archive | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    const update = () => setPage(initialPage());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    fetch("/demo/archive.json", { signal: controller.signal })
      .then(response => { if (!response.ok) throw new Error(`Archive unavailable (HTTP ${response.status}).`); return response.json(); })
      .then(data => setArchive(archiveSchema.parse(data)))
      .catch(error => { if (!controller.signal.aborted) setError(error instanceof Error ? error.message : "Archive could not be verified."); });
    return () => controller.abort();
  }, []);
  const outcome = archive?.outcome;
  const corrected = archive?.confirmed_skill.skill.steps.find(step => step.source_event_id === 31);
  const original = archive?.draft.skill.steps.find(step => step.source_event_id === 31);
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">Skip to content</a>
    <aside className="sidebar">
      <a className="brand" href="#overview"><span className="brand-symbol"><ScanLine size={23} /></span><span>ShadowOps<small>CONTROL CENTER</small></span></a>
      <div className="workspace-label">VERIFIED ARCHIVE</div>
      <nav aria-label="Main navigation">{pages.map(item => <button key={item.id} className={`nav-item ${page === item.id ? "active" : ""}`} aria-current={page === item.id ? "page" : undefined} onClick={() => { setPage(item.id); window.location.hash = item.id; }}><item.icon size={18} /><span>{item.label}</span></button>)}</nav>
      <div className="sidebar-footer"><span>Archived real execution</span><p>Synthetic sandbox data only.</p><a href="https://github.com/kar1m0vf/shadowops/tree/feat/integration" target="_blank" rel="noreferrer">GitHub source</a></div>
    </aside>
    <div className="main-shell">
      <header className="topbar"><span>ShadowOps / Public demo</span><span className="badge" role="status">Archived Verified Demo — Read Only</span></header>
      <main id="main-content">
        <div className="page-title"><div><h1>{pages.find(item => item.id === page)!.label}</h1><p>This is an archived real local run. This website does not perform live remote browser automation.</p></div></div>
        {error ? <ErrorNotice title="Evidence unavailable" message={error} /> : !archive ? <Loading>Loading verified evidence…</Loading> : <>
          {page === "overview" && <div className="feature-stack">
            <Panel title="Learn from a human demonstration" subtitle="Teach → Record → AI Compile → Human Review → Replay"><div className="panel-body"><p className="lead">ShadowOps turns semantic browser demonstrations into AI-proposed workflows that humans review before controlled browser execution.</p><p>This archive preserves a real Qwen3-VL 4B compilation and a human-approved Playwright replay against the fictional local ShadowBank sandbox.</p><div className="metrics"><div><strong>{archive.events.length}</strong><span>Original recorded events</span></div><div><strong>{archive.confirmed_skill.skill.steps.length}</strong><span>Reviewed workflow steps</span></div><div><strong>{archive.replay.results.length}</strong><span>Actual execution attempts</span></div><div><strong>{outcome!.case_id}</strong><span>Verified dispute</span></div></div><p>Recorded example: <code>TXN-81001</code>. Reviewed variable: <code>transaction_id</code>. Replay input: <code>{outcome!.transaction_id}</code> for {outcome!.customer}.</p><button className="button primary" onClick={() => { setPage("demonstration"); window.location.hash = "demonstration"; }}>Inspect the real demonstration</button></div></Panel>
            <Panel title="Public archive, local live system"><div className="panel-body"><p>FastAPI, SQLite, Ollama and the browser executor stay on the developer's computer. Public visitors can inspect evidence, not initiate actions.</p><div className="button-row"><button className="button secondary" disabled>Start recording · Local only</button><button className="button secondary" disabled>Compile skill · Local only</button><button className="button secondary" disabled>Start replay · Local only</button></div><p>Local live mode remains available with <code>npm run dev</code>. This deployment is built with <code>npm run build:demo</code>.</p></div></Panel>
          </div>}
          {page === "demonstration" && <Panel title="Original nine-event demonstration" subtitle={archive.provenance.session_id}><div className="panel-body"><p>Original insertion order, event IDs, semantic targets, allowed synthetic input and checkbox states are preserved.</p><ol className="event-timeline">{archive.events.map((event, index) => <li className="event-row" key={event.id}><div className="event-content"><div className="event-top"><strong>{index + 1}. Event #{event.id}</strong><span className="badge">{event.action}</span><time>{timeLabel(event.timestamp)}</time></div><h3>{event.target.label || event.target.tag || "Navigation"}</h3>{event.value !== undefined && <p>Recorded value: <code>{event.value}</code></p>}{event.checked !== undefined && <p>Checked state: <strong>{String(event.checked)}</strong></p>}<p className="small muted">Recorded page: <code>{event.url}</code></p><details><summary>Original event and semantic locator evidence</summary><JsonView value={event} /></details></div></li>)}</ol></div></Panel>}
          {page === "skill" && <Panel title="Original AI-generated draft" subtitle={`Real model: ${archive.draft.model} · ${archive.draft.id}`}><div className="panel-body"><p>The real model proposed <code>transaction_id</code> from the recorded synthetic input. Its source requires human input; no value source or successful action was invented by this website.</p><p>This is the original proposal, including the incorrect uncheck description corrected during human review. Compare the approved version in Human Review.</p><SkillReview skill={archive.draft.skill} readOnly /></div></Panel>}
          {page === "review" && <div className="feature-stack"><Panel title="Human review and approval" subtitle={archive.confirmed_skill.id}><div className="panel-body"><p><CheckCircle2 size={17} /> Confirmed at {timeLabel(archive.confirmed_skill.confirmed_at)}. Original recording and AI draft were retained.</p><h3>Event 31 correction</h3><p>AI proposal: {original?.description}</p><p>Human correction: <strong>{corrected?.description}</strong></p><p>Recorded and approved checked state: <strong>{String(corrected?.checked)}</strong>.</p><p>The replay paused before dispute creation and continued only after explicit human approval. Its final outcome was independently observed and then confirmed by the user.</p><blockquote>{archive.verification.human_confirmation.statement}</blockquote><button className="button secondary" disabled>Confirm skill · Archived approval</button><details><summary>Preserved final verification evidence</summary><JsonView value={archive.verification} /></details></div></Panel><Panel title="Approved reusable workflow"><div className="panel-body"><SkillReview skill={archive.confirmed_skill.skill} readOnly /></div></Panel></div>}
          {page === "replay" && <div className="feature-stack"><Panel title="Sam Rivera replay — verified final result" subtitle={archive.replay.id}><div className="panel-body"><span className="badge status-completed">{archive.replay.status}</span><p>Outcome verified: <strong>{String(archive.replay.outcome_verified)}</strong>. This status belongs to the archived execution.</p><dl className="settings-list">{Object.entries(outcome!).map(([key, value]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{value}</dd></div>)}</dl><p>Customer ID, transaction ID, amount and currency were independently compared with the visible request before attestation. All four fields matched.</p><details><summary>Runtime parameters and explicit customer context</summary><JsonView value={{ parameters: archive.replay.parameters, context_selection: archive.replay.context_selection }} /></details><figure className="archive-evidence"><img src={archive.screenshots.confirmation} alt="Actual archived ShadowBank confirmation showing DSP-1002 for Sam Rivera, CUS-3072, TXN-81002 and $48.50 USD" /><figcaption>Actual confirmation screenshot from the successful local replay. All displayed records are synthetic.</figcaption></figure><details><summary>Screenshot before the approved dispute creation</summary><figure className="archive-evidence"><img src={archive.screenshots.before_dispute} alt="Archived pause before creating the dispute, with matching customer and transaction details" /></figure></details></div></Panel><Panel title="Real execution timeline" subtitle="All attempts are retained, including pauses before human approval"><div className="panel-body"><ol className="replay-timeline">{archive.replay.results.map((result, index) => <li className="review-card" key={index}><div className="review-card-heading"><strong>Step {result.step} · {result.action}</strong><span className={`badge status-${result.status}`}>{result.status}</span></div><p>{result.detail}</p><span className="small muted">{timeLabel(result.timestamp)} · Source event {result.source_event_id ?? "explicit setup / verification"}</span></li>)}</ol><button className="button secondary" disabled>Resume replay · Archived execution</button></div></Panel></div>}
          {page === "limitations" && <Panel title="MVP limitations and evidence provenance"><div className="panel-body"><ul className="message-list"><li>This website shows an archived real run, not live automation or a simulated run.</li><li>Live teaching, inference and replay require the local Python services and visible Chromium. They are not exposed publicly.</li><li>Human review is required for variable sources, ambiguity, consequential clicks, attestations and final outcome.</li><li>Replay is limited to explicitly configured local test origins and a small action vocabulary. General website reliability has not been established.</li><li>Field values are denied by default; only allowlisted non-sensitive synthetic input is recorded.</li><li>ShadowBank stores its demo state in browser memory. The archive preserves proof of the earlier DSP-1002 run; opening a new sandbox tab does not restore that session.</li><li>The full fresh workflow through the local frontend was not repeated during integration. Saved-data UI checks and real preflight passed.</li></ul><p>Verified local results: <strong>152 backend tests, 14 frontend tests, 42 real Chromium integration checks</strong>; both production builds passed. Automated LLM mocks are test fixtures and are not evidence of real learning.</p><p>Only selected synthetic JSON and two inspected screenshots were published. SQLite, credentials, machine paths and other local artifacts are excluded.</p><details><summary>Source artifact hashes and archive date</summary><JsonView value={archive.provenance} /></details><a className="text-button" href="/demo/archive.json" download>Download the sanitized evidence JSON</a></div></Panel>}
        </>}
        <footer className="app-footer"><span>ShadowOps / Hackathon MVP</span><span>Archived Verified Demo — Read Only</span></footer>
      </main>
    </div>
  </div>;
}
