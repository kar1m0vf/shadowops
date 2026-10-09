import { useEffect, useRef, useState } from "react";
import type { Archive } from "./archive";
import { requests, transactions, validateTransaction, createDispute, money, type Request, type Transaction, type Dispute } from "./syntheticBank";

type Bank = { request?: Request; transaction?: Transaction; value: string; checked: boolean; view: string; dispute?: Dispute };
const examples = ["Find Sam Rivera's transaction", "Check transaction TXN-81002", "Prepare a dispute for this transaction", "Show me what you are doing", "Run the approved workflow"];
export default function GuidedSandbox({ archive }: { archive: Archive }) {
  const current = useRef<Bank>({ value: "", checked: false, view: "Inbox" });
  const [bank, setBank] = useState(current.current);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState(["Guided replay uses the saved AI-compiled skill. Choose an example below. No new AI inference runs here."]);
  const [logs, setLogs] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [pending, setPending] = useState<number | null>(null);
  const [active, setActive] = useState("Ready");
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  function update(patch: Partial<Bank>) { current.current = { ...current.current, ...patch }; setBank(current.current); }
  function say(message: string) { setMessages(items => [...items, message]); }
  function log(message: string) { setLogs(items => [...items, `${new Date().toLocaleTimeString()} · ${message}`]); setActive(message); }
  function check() {
    const state = current.current;
    if (!state.request) throw new Error("Select a customer request first.");
    const transaction = transactions.find(item => item.id === state.value);
    update({ transaction, checked: false });
    const validation = validateTransaction(state.request, transaction);
    log(validation.message);
    if (!validation.valid) throw new Error(validation.message);
    return transaction!;
  }
  async function run(start = 0) {
    setBusy(true);
    try {
      if (!current.current.request) throw new Error("Choose a customer first; transaction_id is supplied by you, not inferred by AI.");
      for (let index = start; index < archive.confirmed_skill.skill.steps.length; index++) {
        await new Promise(resolve => setTimeout(resolve, 450));
        if (!mounted.current) return;
        const step = archive.confirmed_skill.skill.steps[index];
        const label = step.target?.label?.toLowerCase() ?? "";
        setActive(`Step ${index + 1}: ${step.description}`);
        if (step.action === "navigate") update({ view: "Inbox" });
        else if (step.action === "fill") update({ value: current.current.value || current.current.request!.transactionId, checked: false });
        else if (step.action === "set_checked") {
          if (step.checked) check();
          update({ checked: step.checked === true });
        } else if (step.action === "click" && label.includes("create dispute")) {
          check(); update({ checked: true });
          setPending(index); say("Paused before simulated case creation. Compare all four displayed fields and approve explicitly. No real bank data will change.");
          log(`Step ${index + 1} · event ${step.source_event_id}: waiting for human approval`); return;
        } else if (step.action === "click" && label.includes("search")) check();
        else if (step.action === "click" && label.includes("investigate")) update({ view: "Investigation" });
        else if (step.action === "click" && label.includes("back")) update({ view: "Inbox" });
        else throw new Error(`Unsupported recorded action: ${step.action} / ${label}. Paused safely.`);
        log(`Step ${index + 1} · event ${step.source_event_id}: ${step.description} — simulated`);
      }
      say("Guided workflow completed in isolated browser state. The real archived result remains DSP-1002.");
    } catch (error) { say(error instanceof Error ? error.message : "Paused safely."); log("Blocked / human input required"); }
    finally { if (mounted.current) setBusy(false); }
  }
  function command(text: string) {
    if (busy || pending !== null) return;
    setInput(""); say(`You: ${text}`);
    try {
      const normalized = text.trim().toLowerCase();
      if (normalized === "run the approved workflow") { void run(); return; }
      if (normalized === "show me what you are doing") { say(`${active}. Customer: ${current.current.request?.name ?? "not selected"}; transaction: ${current.current.transaction?.id ?? "not found"}. See the live timeline below.`); return; }
      const customer = requests.find(item => normalized === `find ${item.name.toLowerCase()}'s transaction`);
      if (customer) { update({ request: customer, value: customer.transactionId, transaction: undefined, checked: false, dispute: undefined, view: "Investigation" }); log(`Selected ${customer.name} / ${customer.customerId}`); check(); say("Transaction found. All four fields match the selected synthetic request."); return; }
      const match = /^check transaction (txn-\d+)$/i.exec(text.trim());
      if (match) {
        const value = match[1].toUpperCase();
        const request = current.current.request ?? requests.find(item => item.transactionId === value);
        update({ request, value, view: "Investigation", dispute: undefined }); check(); say("Customer ID, transaction ID, amount and currency match."); return;
      }
      if (normalized === "prepare a dispute for this transaction") { check(); update({ checked: true }); setPending(-1); log("Prepared synthetic dispute; awaiting explicit approval"); say("Review the matching details, then approve the simulated write."); return; }
      say("Unsupported command. Use the listed guided examples. Arbitrary URLs, code and external actions are disabled.");
    } catch (error) { say(error instanceof Error ? error.message : "Blocked."); log("Validation blocked the action"); }
  }
  function approve() {
    try {
      const state = current.current;
      if (!state.request) throw new Error("Customer missing.");
      const dispute = createDispute(state.request, state.transaction, state.checked, state.dispute ? [state.dispute] : []);
      dispute.id = `SIM-${state.request.id.slice(4)}`;
      update({ dispute, view: "Simulated confirmation" });
      log(`Human approved simulated write: ${dispute.id} / ${dispute.transactionId}`);
      say(`Simulated case ${dispute.id} created. No backend or real bank state changed.`);
      const next = pending; setPending(null);
      if (next !== null && next >= 0) void run(next + 1);
    } catch (error) { say(error instanceof Error ? error.message : "Blocked."); }
  }
  const valid = bank.request ? validateTransaction(bank.request, bank.transaction) : null;
  return <div className="feature-stack guided-demo">
    <div className="notice"><strong>Interactive Sandbox — Guided Replay</strong><p>Deterministic commands drive isolated synthetic state using the real approved skill. No new inference, remote browser execution or real dispute creation. Archived proof remains available in Replay &amp; Result.</p></div>
    <div className="guided-columns">
      <section className="panel"><div className="panel-body"><h2>Talk to ShadowOps</h2><div className="guided-messages" aria-live="polite">{messages.map((message, index) => <p key={index}>{message}</p>)}</div><form onSubmit={event => { event.preventDefault(); command(input); }}><label htmlFor="guided-command">Guided command</label><input id="guided-command" value={input} onChange={event => setInput(event.target.value)} disabled={busy || pending !== null} maxLength={200} placeholder="Find Sam Rivera's transaction" /><button className="button primary" disabled={busy || pending !== null || !input.trim()}>Send command</button></form><div className="guided-examples">{examples.map(example => <button className="button secondary" key={example} disabled={busy || pending !== null} onClick={() => command(example)}>{example}</button>)}</div></div></section>
      <section className="panel"><div className="panel-body"><h2>ShadowBank · Synthetic sandbox</h2><span className="badge">{bank.view}</span><p className="guided-active" role="status">{active}</p><div className="guided-examples">{requests.map(request => <button key={request.id} disabled={busy || pending !== null} className={`button ${bank.request?.id === request.id ? "primary" : "secondary"}`} onClick={() => { update({ request, value: request.transactionId, transaction: undefined, checked: false, dispute: undefined }); log(`Selected ${request.name}`); }}>{request.name}</button>)}</div>{bank.request && <><h3>{bank.request.name}</h3><p>{bank.request.message}</p><p>Request: {bank.request.customerId} · {bank.request.transactionId} · {money(bank.request.amountCents)} {bank.request.currency}</p></>}<label htmlFor="sandbox-transaction">Transaction ID · human input parameter</label><input id="sandbox-transaction" value={bank.value} disabled={busy || pending !== null} onChange={event => update({ value: event.target.value, transaction: undefined, checked: false, dispute: undefined })} /><button className="button secondary" disabled={busy || pending !== null} onClick={() => command(`Check transaction ${bank.value}`)}>Search transaction</button>{bank.transaction && <div className="guided-result"><h3>Found {bank.transaction.id}</h3><p>{bank.transaction.customerId} · {bank.transaction.merchant}</p><p>{money(bank.transaction.amountCents)} {bank.transaction.currency}</p><strong>{valid?.message}</strong></div>}<p><label><input type="checkbox" checked={bank.checked} readOnly /> Synthetic details verified: {String(bank.checked)}</label></p>{pending !== null && <div className="guided-approval"><h3>Human approval required</h3><p>Approve only this isolated simulated case. Check the customer, transaction, amount and currency above.</p><button className="button primary" onClick={approve}>Approve simulated dispute</button><button className="button secondary" onClick={() => { setPending(null); log("Human cancelled simulated write"); }}>Cancel</button></div>}{bank.dispute && <p className="guided-result"><strong>Simulated case {bank.dispute.id}</strong> · {bank.dispute.transactionId} · {money(bank.dispute.amountCents)} {bank.dispute.currency}</p>}</div></section>
    </div><section className="panel"><div className="panel-body"><h2>Live action timeline · simulated</h2><p>Source skill: {archive.confirmed_skill.id}. Original event IDs accompany the executed graph.</p><ol aria-live="polite">{logs.map((item, index) => <li key={index}>{item}</li>)}</ol>{logs.length === 0 && <p>Waiting for a guided command.</p>}</div></section>
  </div>;
}
