import { useState, useRef, useEffect } from "react";

const API = "https://cinch-agent-production.up.railway.app";
const DEMO_CUSTOMER = "demo-customer-001";

const api = async (path, opts = {}) => {
  const res = await fetch(`${API}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) throw new Error((await res.json()).detail || res.statusText);
  return res.json();
};

const Icon = ({ d, size = 18, color = "currentColor" }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
    stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
    <path d={d} />
  </svg>
);
const ICONS = {
  upload:   "M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12",
  project:  "M3 7h18M3 12h18M3 17h18",
  check:    "M20 6L9 17l-5-5",
  book:     "M4 19.5A2.5 2.5 0 016.5 17H20M4 19.5A2.5 2.5 0 014 17V4h16v13.5",
  pin:      "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
  send:     "M22 2L11 13M22 2L15 22l-4-9-9-4 20-7z",
  analyze:  "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z",
  lock:     "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  alert:    "M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0zM12 9v4M12 17h.01",
  x:        "M18 6L6 18M6 6l12 12",
};

const C = {
  bg: "#0f1117", surface: "#1a1d27", border: "#2a2d3e",
  accent: "#3b82f6", accentLight: "#60a5fa",
  success: "#10b981", warning: "#f59e0b", error: "#ef4444",
  proprietary: "#a855f7",
  textPrimary: "#e2e8f0", textSecondary: "#94a3b8", textMuted: "#64748b",
};

const card = { background: C.surface, border: `1px solid ${C.border}`, borderRadius: 12, padding: 20 };

const badge = (color) => ({
  display: "inline-flex", alignItems: "center", gap: 4,
  padding: "2px 8px", borderRadius: 20, fontSize: 11, fontWeight: 600,
  background: color + "22", color, border: `1px solid ${color}44`,
});

const inputStyle = {
  background: C.bg, border: `1px solid ${C.border}`, borderRadius: 8,
  padding: "10px 14px", color: C.textPrimary, fontSize: 14, outline: "none",
  boxSizing: "border-box", fontFamily: "inherit",
};

const btn = (active, color = C.accent) => ({
  background: active ? color : C.border, color: "#fff", border: "none",
  borderRadius: 8, padding: "10px 16px", fontWeight: 600,
  cursor: active ? "pointer" : "not-allowed", fontSize: 14,
  display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
});

// ── Status badge for compliance items ────────────────────────────────────────
const STATUS_COLOR = {
  PASS: C.success, FAIL: C.error,
  NEEDS_REVIEW: C.warning, NOT_FOUND: C.textMuted,
};
const STATUS_ICON = {
  PASS: ICONS.check, FAIL: ICONS.x,
  NEEDS_REVIEW: ICONS.alert, NOT_FOUND: ICONS.book,
};


// ── Upload Panel ─────────────────────────────────────────────────────────────
function UploadPanel({ onUploaded }) {
  const [file, setFile]       = useState(null);
  const [name, setName]       = useState("");
  const [year, setYear]       = useState(new Date().getFullYear());
  const [docType, setDocType] = useState("standard");
  const [uploading, setUploading] = useState(false);
  const [result, setResult]   = useState(null);
  const fileRef = useRef();

  const handleUpload = async () => {
    if (!file || !name || !year) return;
    setUploading(true); setResult(null);
    try {
      const fd = new FormData();
      fd.append("customer_id", DEMO_CUSTOMER);
      fd.append("standard_name", name);
      fd.append("edition_year", year);
      fd.append("doc_type", docType);
      fd.append("file", file);
      const res = await fetch(`${API}/standards/upload`, { method: "POST", body: fd });
      const data = await res.json();
      setResult({ ok: true, msg: `Upload started! ID: ${data.standard_id}` });
      onUploaded?.();
      setFile(null); setName(""); setYear(new Date().getFullYear()); setDocType("standard");
    } catch (e) {
      setResult({ ok: false, msg: e.message });
    } finally { setUploading(false); }
  };

  const docTypeColor = { standard: C.accent, design_guide: C.warning, proprietary: C.proprietary };

  return (
    <div style={card}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 18 }}>
        <Icon d={ICONS.upload} color={C.accent} />
        <span style={{ fontWeight: 700, color: C.textPrimary, fontSize: 15 }}>Upload Document</span>
      </div>

      {/* Doc type selector */}
      <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
        {[
          { value: "standard",     label: "Public Standard",  note: "ASHRAE, SMACNA, IMC…" },
          { value: "design_guide", label: "Design Guide",     note: "Internal reference" },
          { value: "proprietary",  label: "Proprietary",      note: "Confidential — isolated" },
        ].map(t => (
          <div key={t.value}
            onClick={() => setDocType(t.value)}
            style={{
              flex: 1, padding: "10px 12px", borderRadius: 8, cursor: "pointer",
              border: `1px solid ${docType === t.value ? docTypeColor[t.value] : C.border}`,
              background: docType === t.value ? docTypeColor[t.value] + "22" : C.bg,
              textAlign: "center",
            }}>
            <div style={{ fontWeight: 600, fontSize: 13,
              color: docType === t.value ? docTypeColor[t.value] : C.textSecondary }}>
              {t.value === "proprietary" && <Icon d={ICONS.lock} size={12} />} {t.label}
            </div>
            <div style={{ fontSize: 11, color: C.textMuted, marginTop: 2 }}>{t.note}</div>
          </div>
        ))}
      </div>

      {docType === "proprietary" && (
        <div style={{
          background: C.proprietary + "11", border: `1px solid ${C.proprietary}44`,
          borderRadius: 8, padding: "10px 14px", marginBottom: 12, fontSize: 12,
          color: C.proprietary, display: "flex", gap: 8, alignItems: "flex-start",
        }}>
          <Icon d={ICONS.lock} size={14} />
          <span>Proprietary documents are stored in your isolated sandbox.
          They are never retrievable by other customers or cross-contaminated with shared standards.</span>
        </div>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        <input style={{ ...inputStyle, width: "100%" }}
          placeholder="Document name (e.g. ASHRAE 62.1 or My Design Guide)"
          value={name} onChange={e => setName(e.target.value)} />
        <input style={{ ...inputStyle, width: "100%" }} type="number"
          placeholder="Edition / year (e.g. 2022)"
          value={year} onChange={e => setYear(+e.target.value)} />
        <div onClick={() => fileRef.current.click()} style={{
          ...inputStyle, cursor: "pointer",
          color: file ? C.textPrimary : C.textMuted,
          display: "flex", alignItems: "center", gap: 8,
        }}>
          <Icon d={ICONS.book} size={14} color={C.textMuted} />
          {file ? file.name : "Select PDF file…"}
        </div>
        <input ref={fileRef} type="file" accept=".pdf" style={{ display: "none" }}
          onChange={e => setFile(e.target.files[0])} />

        <button onClick={handleUpload} disabled={!file || !name || !year || uploading}
          style={btn(!(!file || !name || !year || uploading))}>
          {uploading ? "Uploading…" : "Upload & Index"}
        </button>
      </div>

      {result && (
        <div style={{
          marginTop: 12, padding: "10px 14px", borderRadius: 8, fontSize: 13,
          background: result.ok ? C.success + "22" : C.error + "22",
          color: result.ok ? C.success : C.error,
        }}>{result.msg}</div>
      )}
    </div>
  );
}

// ── Library ───────────────────────────────────────────────────────────────────
function StandardsLibrary({ standards, loading }) {
  const statusColor = { ready: C.success, processing: C.warning, error: C.error };
  const docColor    = { standard: C.accent, design_guide: C.warning, proprietary: C.proprietary };

  return (
    <div style={card}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <Icon d={ICONS.book} color={C.accent} />
        <span style={{ fontWeight: 700, color: C.textPrimary, fontSize: 15 }}>
          Your Library ({standards.length})
        </span>
      </div>
      {loading && <p style={{ color: C.textMuted, fontSize: 13 }}>Loading…</p>}
      {!loading && standards.length === 0 &&
        <p style={{ color: C.textMuted, fontSize: 13 }}>No documents uploaded yet.</p>}
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {standards.map(s => {
          const dtype = s.display_label?.includes("PROPRIETARY") ? "proprietary"
                      : s.display_label?.includes("Design Guide") ? "design_guide"
                      : "standard";
          return (
            <div key={s.id} style={{
              background: C.bg, border: `1px solid ${C.border}`,
              borderRadius: 8, padding: "10px 14px",
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontWeight: 600, color: C.textPrimary, fontSize: 14 }}>
                    {s.standard_name} <span style={{ color: C.accentLight }}>{s.edition_year}</span>
                  </span>
                  {dtype !== "standard" && (
                    <span style={badge(docColor[dtype])}>
                      {dtype === "proprietary" && <Icon d={ICONS.lock} size={9} />}
                      {dtype === "proprietary" ? "Proprietary" : "Design Guide"}
                    </span>
                  )}
                </div>
                <div style={{ color: C.textMuted, fontSize: 12, marginTop: 2 }}>
                  {s.total_pages} pages · {s.total_chunks} chunks indexed
                </div>
              </div>
              <span style={badge(statusColor[s.status] || C.textMuted)}>
                {s.status === "ready" && <Icon d={ICONS.check} size={10} />}
                {s.status}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Projects ──────────────────────────────────────────────────────────────────
function ProjectManager({ projects, standards, onProjectCreated, onStandardPinned }) {
  const [newName, setNewName]   = useState("");
  const [newJur, setNewJur]     = useState("");
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState(null);
  const [pinStd, setPinStd]     = useState("");

  const handleCreate = async () => {
    if (!newName) return;
    setCreating(true);
    try {
      await api("/projects", { method: "POST",
        body: JSON.stringify({ customer_id: DEMO_CUSTOMER, name: newName, jurisdiction: newJur }) });
      setNewName(""); setNewJur("");
      onProjectCreated?.();
    } catch (e) { alert(e.message); }
    finally { setCreating(false); }
  };

  const handlePin = async () => {
    if (!selected || !pinStd) return;
    try {
      await api(`/projects/${selected}/standards?customer_id=${DEMO_CUSTOMER}`, {
        method: "POST", body: JSON.stringify({ uploaded_standard_id: pinStd }),
      });
      setPinStd(""); onStandardPinned?.();
    } catch (e) { alert(e.message); }
  };

  const ready = standards.filter(s => s.status === "ready");
  const docColor = { standard: C.accent, design_guide: C.warning, proprietary: C.proprietary };

  return (
    <div style={card}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
        <Icon d={ICONS.project} color={C.accent} />
        <span style={{ fontWeight: 700, color: C.textPrimary, fontSize: 15 }}>
          Projects ({projects.length})
        </span>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input style={{ ...inputStyle, flex: 2 }} placeholder="Project name"
          value={newName} onChange={e => setNewName(e.target.value)} />
        <input style={{ ...inputStyle, flex: 1 }} placeholder="Jurisdiction"
          value={newJur} onChange={e => setNewJur(e.target.value)} />
        <button onClick={handleCreate} disabled={!newName || creating}
          style={{ ...btn(!!newName), whiteSpace: "nowrap", padding: "10px 14px" }}>
          + Create
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
        {projects.map(p => (
          <div key={p.id}
            onClick={() => setSelected(selected === p.id ? null : p.id)}
            style={{
              background: selected === p.id ? C.accent + "22" : C.bg,
              border: `1px solid ${selected === p.id ? C.accent : C.border}`,
              borderRadius: 8, padding: "10px 14px", cursor: "pointer",
            }}>
            <div style={{ fontWeight: 600, color: C.textPrimary, fontSize: 14 }}>
              {p.name}
              {p.jurisdiction && <span style={{ color: C.textMuted, fontWeight: 400, marginLeft: 8, fontSize: 12 }}>
                ({p.jurisdiction})
              </span>}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 6 }}>
              {p.pinned_standards.length === 0
                ? <span style={{ color: C.textMuted, fontSize: 12 }}>No documents pinned</span>
                : p.pinned_standards.map(s => {
                    const dtype = s.display_label?.includes("PROPRIETARY") ? "proprietary"
                                : s.display_label?.includes("Design Guide") ? "design_guide"
                                : "standard";
                    return (
                      <span key={s.display_label} style={badge(docColor[dtype])}>
                        {dtype === "proprietary" && <Icon d={ICONS.lock} size={9} />}
                        {s.standard_name} {s.edition_year}
                      </span>
                    );
                  })
              }
            </div>
          </div>
        ))}
      </div>

      {selected && ready.length > 0 && (
        <div style={{ display: "flex", gap: 8 }}>
          <select style={{ ...inputStyle, flex: 1 }}
            value={pinStd} onChange={e => setPinStd(e.target.value)}>
            <option value="">Pin a document to this project…</option>
            {ready.map(s => (
              <option key={s.id} value={s.id}>{s.display_label || `${s.standard_name} ${s.edition_year}`}</option>
            ))}
          </select>
          <button onClick={handlePin} disabled={!pinStd}
            style={{ ...btn(!!pinStd, C.success), padding: "10px 14px" }}>
            Pin
          </button>
        </div>
      )}
    </div>
  );
}

// ── Citation card ─────────────────────────────────────────────────────────────
function CitationCard({ c, index }) {
  const [open, setOpen] = useState(false);
  const isProp = c.doc_type === "proprietary";
  const color  = isProp ? C.proprietary : c.doc_type === "design_guide" ? C.warning : C.accent;
  return (
    <div style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 8 }}>
      <div onClick={() => setOpen(!open)}
        style={{ padding: "10px 14px", cursor: "pointer",
          display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
            <span style={badge(color)}>{index}</span>
            <span style={{ fontWeight: 700, color, fontSize: 13 }}>
              {isProp && <Icon d={ICONS.lock} size={11} />} {c.standard_name} {c.edition_year}
            </span>
          </div>
          <div style={{ color: C.textPrimary, fontSize: 13, fontFamily: "monospace" }}>
            § {c.section_number}
            {c.section_title && <span style={{ color: C.textSecondary, fontFamily: "inherit" }}> — {c.section_title}</span>}
          </div>
          <div style={{ color: C.textMuted, fontSize: 11, marginTop: 2 }}>
            Page {c.page_number} · {open ? "collapse" : "see excerpt"}
          </div>
        </div>
      </div>
      {open && (
        <div style={{ padding: "0 14px 12px", borderTop: `1px solid ${C.border}`, paddingTop: 10 }}>
          <p style={{ color: C.textSecondary, fontSize: 12, lineHeight: 1.6, margin: 0 }}>
            {c.excerpt}
          </p>
        </div>
      )}
    </div>
  );
}

// ── Chat ──────────────────────────────────────────────────────────────────────
function ChatPanel({ projects }) {
  const [selProject, setSelProject] = useState("");
  const [question, setQuestion]     = useState("");
  const [messages, setMessages]     = useState([]);
  const [loading, setLoading]       = useState(false);
  const bottomRef = useRef();

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const handleQuery = async () => {
    if (!question.trim() || !selProject || loading) return;
    const q = question.trim(); setQuestion("");
    setMessages(m => [...m, { role: "user", text: q }]);
    setLoading(true);
    try {
      const data = await api("/query", { method: "POST",
        body: JSON.stringify({ customer_id: DEMO_CUSTOMER, project_id: selProject, question: q }) });
      setMessages(m => [...m, { role: "assistant", ...data }]);
    } catch (e) {
      setMessages(m => [...m, { role: "error", text: e.message }]);
    } finally { setLoading(false); }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ ...card, marginBottom: 12 }}>
        <select style={{ ...inputStyle, width: "100%" }}
          value={selProject} onChange={e => setSelProject(e.target.value)}>
          <option value="">Select a project to query…</option>
          {projects.map(p => (
            <option key={p.id} value={p.id}>
              {p.name} ({p.pinned_standards.map(s => `${s.standard_name} ${s.edition_year}`).join(", ") || "no docs"})
            </option>
          ))}
        </select>
      </div>

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 12, marginBottom: 12, minHeight: 300 }}>
        {messages.length === 0 && (
          <div style={{ ...card, textAlign: "center", color: C.textMuted, fontSize: 14, padding: 32 }}>
            <Icon d={ICONS.book} size={32} color={C.border} />
            <p style={{ margin: "12px 0 4px" }}>Ask a question about your standards or design guides</p>
            <p style={{ fontSize: 12 }}>e.g. "What is the minimum OA rate for an open office?"</p>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i}>
            {m.role === "user" && (
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <div style={{ background: C.accent + "33", border: `1px solid ${C.accent}44`,
                  borderRadius: "12px 12px 2px 12px", padding: "10px 14px",
                  maxWidth: "80%", color: C.textPrimary, fontSize: 14 }}>
                  {m.text}
                </div>
              </div>
            )}
            {m.role === "assistant" && (
              <div style={card}>
                {m.standards_consulted?.length > 0 && (
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
                    {m.standards_consulted.map(s => (
                      <span key={s} style={badge(C.success)}>
                        <Icon d={ICONS.check} size={9} /> {s}
                      </span>
                    ))}
                  </div>
                )}
                {m.warning && (
                  <div style={{ background: C.warning + "22", border: `1px solid ${C.warning}44`,
                    borderRadius: 6, padding: "6px 10px", marginBottom: 10, color: C.warning, fontSize: 12 }}>
                    ⚠ {m.warning}
                  </div>
                )}
                <p style={{ color: C.textPrimary, fontSize: 14, lineHeight: 1.7, margin: 0, whiteSpace: "pre-wrap" }}>
                  {m.answer}
                </p>
                {m.citations?.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div style={{ color: C.textMuted, fontSize: 11, fontWeight: 700,
                      textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>
                      Citations — verify in your copy
                    </div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                      {m.citations.map((c, j) => <CitationCard key={j} c={c} index={j+1} />)}
                    </div>
                  </div>
                )}
              </div>
            )}
            {m.role === "error" && (
              <div style={{ color: C.error, fontSize: 13, padding: "8px 12px" }}>Error: {m.text}</div>
            )}
          </div>
        ))}
        {loading && (
          <div style={{ ...card, display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{ width: 16, height: 16, borderRadius: "50%",
              border: `2px solid ${C.border}`, borderTopColor: C.accent,
              animation: "spin 0.8s linear infinite" }} />
            <span style={{ color: C.textMuted, fontSize: 13 }}>Searching standards…</span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <textarea style={{ ...inputStyle, flex: 1, minHeight: 60, lineHeight: 1.5, resize: "none" }}
          placeholder={selProject ? "Ask about a code requirement…" : "Select a project first"}
          value={question} onChange={e => setQuestion(e.target.value)} disabled={!selProject}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleQuery(); } }} />
        <button onClick={handleQuery} disabled={!question.trim() || !selProject || loading}
          style={{ ...btn(!!question.trim() && !!selProject), width: 48, padding: 0 }}>
          <Icon d={ICONS.send} size={18} />
        </button>
      </div>
    </div>
  );
}

// ── Compliance Analysis Panel ─────────────────────────────────────────────────
function AnalyzePanel({ projects }) {
  const [selProject, setSelProject] = useState("");
  const [input, setInput]           = useState("");
  const [report, setReport]         = useState(null);
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState("");

  const EXAMPLE = `Space type: open office
Floor area: 2,000 sq ft
Design occupancy: 20 people
Supply air CFM: 800
Minimum OA CFM (design): 220
System type: VAV with demand-controlled ventilation
Refrigerant: R-410A`;

  const handleAnalyze = async () => {
    if (!input.trim() || !selProject || loading) return;
    setLoading(true); setReport(null); setError("");
    try {
      const data = await api("/analyze", { method: "POST",
        body: JSON.stringify({ customer_id: DEMO_CUSTOMER, project_id: selProject, design_input: input }) });
      setReport(data);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const statusBg = {
    PASS: C.success, FAIL: C.error, NEEDS_REVIEW: C.warning, NOT_FOUND: C.textMuted
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={card}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
          <Icon d={ICONS.analyze} color={C.accent} />
          <span style={{ fontWeight: 700, color: C.textPrimary, fontSize: 15 }}>
            Code Compliance Analysis
          </span>
        </div>
        <p style={{ color: C.textSecondary, fontSize: 13, marginBottom: 14 }}>
          Paste design parameters or a spec excerpt. The agent checks it against your project's
          pinned standards and returns a PASS / FAIL / NEEDS REVIEW checklist with citations.
        </p>

        <select style={{ ...inputStyle, width: "100%", marginBottom: 10 }}
          value={selProject} onChange={e => setSelProject(e.target.value)}>
          <option value="">Select a project…</option>
          {projects.map(p => (
            <option key={p.id} value={p.id}>
              {p.name} — {p.pinned_standards.map(s => `${s.standard_name} ${s.edition_year}`).join(", ") || "no standards"}
            </option>
          ))}
        </select>

        <textarea
          style={{ ...inputStyle, width: "100%", minHeight: 160, lineHeight: 1.6,
            resize: "vertical", marginBottom: 10 }}
          placeholder={`Enter design parameters or paste spec text, e.g.:\n\n${EXAMPLE}`}
          value={input}
          onChange={e => setInput(e.target.value)}
        />

        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={handleAnalyze} disabled={!input.trim() || !selProject || loading}
            style={btn(!!input.trim() && !!selProject, C.accent)}>
            {loading
              ? <><div style={{ width: 14, height: 14, borderRadius: "50%",
                  border: `2px solid #fff4`, borderTopColor: "#fff",
                  animation: "spin 0.8s linear infinite" }} /> Analyzing…</>
              : <><Icon d={ICONS.analyze} size={15} /> Run Compliance Check</>
            }
          </button>
          <button onClick={() => setInput(EXAMPLE)}
            style={{ ...btn(true, C.textMuted), background: C.border }}>
            Load Example
          </button>
        </div>

        {error && (
          <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 8,
            background: C.error + "22", color: C.error, fontSize: 13 }}>
            {error}
          </div>
        )}
      </div>

      {report && (
        <div style={card}>
          {/* Score banner */}
          <div style={{ display: "flex", gap: 12, marginBottom: 20, flexWrap: "wrap" }}>
            {[
              { label: "PASS",         count: report.pass_count,   color: C.success },
              { label: "FAIL",         count: report.fail_count,   color: C.error },
              { label: "NEEDS REVIEW", count: report.review_count, color: C.warning },
            ].map(s => (
              <div key={s.label} style={{
                flex: 1, minWidth: 100, background: s.color + "22",
                border: `1px solid ${s.color}44`, borderRadius: 10,
                padding: "12px 16px", textAlign: "center",
              }}>
                <div style={{ fontSize: 28, fontWeight: 800, color: s.color }}>{s.count}</div>
                <div style={{ fontSize: 11, fontWeight: 700, color: s.color, letterSpacing: 0.5 }}>{s.label}</div>
              </div>
            ))}
          </div>

          {/* Standards consulted */}
          {report.standards_consulted?.length > 0 && (
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 14 }}>
              {report.standards_consulted.map(s => (
                <span key={s} style={badge(C.accentLight)}>{s}</span>
              ))}
            </div>
          )}

          {/* Summary */}
          {report.summary && (
            <div style={{ background: C.bg, border: `1px solid ${C.border}`,
              borderRadius: 8, padding: "12px 14px", marginBottom: 16, fontSize: 13,
              color: C.textSecondary, lineHeight: 1.6 }}>
              {report.summary}
            </div>
          )}

          {/* Checklist */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {report.items.map((item, i) => {
              const color = statusBg[item.status] || C.textMuted;
              return (
                <div key={i} style={{
                  background: C.bg, border: `1px solid ${color}44`,
                  borderLeft: `3px solid ${color}`, borderRadius: 8, padding: "12px 14px",
                }}>
                  <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
                    <span style={{ ...badge(color), flexShrink: 0, marginTop: 1 }}>
                      <Icon d={STATUS_ICON[item.status] || ICONS.book} size={10} />
                      {item.status.replace("_", " ")}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, color: C.textPrimary, fontSize: 13, marginBottom: 4 }}>
                        {item.requirement}
                      </div>
                      <div style={{ color: C.textSecondary, fontSize: 13, marginBottom: 6 }}>
                        {item.finding}
                      </div>
                      {(item.calculated_value || item.design_value) && (
                        <div style={{ display: "flex", gap: 16, marginBottom: 6 }}>
                          {item.calculated_value && (
                            <div style={{ fontSize: 12 }}>
                              <span style={{ color: C.textMuted }}>Code requires: </span>
                              <span style={{ color: C.textPrimary, fontFamily: "monospace" }}>{item.calculated_value}</span>
                            </div>
                          )}
                          {item.design_value && (
                            <div style={{ fontSize: 12 }}>
                              <span style={{ color: C.textMuted }}>Design provides: </span>
                              <span style={{ color: item.status === "PASS" ? C.success : item.status === "FAIL" ? C.error : C.textPrimary, fontFamily: "monospace" }}>
                                {item.design_value}
                              </span>
                            </div>
                          )}
                        </div>
                      )}
                      {item.citations?.length > 0 && (
                        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                          {item.citations.map((c, j) => (
                            <span key={j} style={badge(C.accentLight)}>
                              {c.standard_name} {c.edition_year} § {c.section_number} (p.{c.page_number})
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {report.warning && (
            <div style={{ marginTop: 12, padding: "10px 14px", borderRadius: 8,
              background: C.warning + "22", color: C.warning, fontSize: 12 }}>
              ⚠ {report.warning}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


// ── App ───────────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab]           = useState("chat");
  const [standards, setStandards] = useState([]);
  const [projects, setProjects]   = useState([]);
  const [loadingStds, setLoadingStds] = useState(false);

  const loadStandards = async () => {
    setLoadingStds(true);
    try { setStandards(await api(`/standards?customer_id=${DEMO_CUSTOMER}`)); }
    catch {} finally { setLoadingStds(false); }
  };
  const loadProjects = async () => {
    try { setProjects(await api(`/projects?customer_id=${DEMO_CUSTOMER}`)); } catch {}
  };

  useEffect(() => { loadStandards(); loadProjects(); }, []);

  const TABS = [
    { id: "chat",     label: "Query",    icon: ICONS.send },
    { id: "analyze",  label: "Analyze",  icon: ICONS.analyze },
    { id: "library",  label: "Library",  icon: ICONS.book },
    { id: "projects", label: "Projects", icon: ICONS.project },
    { id: "upload",   label: "Upload",   icon: ICONS.upload },
  ];

  return (
    <div style={{ background: C.bg, minHeight: "100vh", fontFamily: "system-ui, sans-serif", color: C.textPrimary }}>
      <style>{`
        * { box-sizing: border-box; }
        @keyframes spin { to { transform: rotate(360deg); } }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: ${C.bg}; }
        ::-webkit-scrollbar-thumb { background: ${C.border}; border-radius: 3px; }
        select option { background: ${C.surface}; }
      `}</style>

      <div style={{ background: C.surface, borderBottom: `1px solid ${C.border}`,
        padding: "0 24px", display: "flex", alignItems: "center",
        justifyContent: "space-between", height: 56 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 30, height: 30, background: C.accent, borderRadius: 8,
            display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Icon d={ICONS.book} size={16} color="#fff" />
          </div>
          <span style={{ fontWeight: 800, fontSize: 16, letterSpacing: -0.3 }}>HVAC Standards Agent</span>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              background: tab === t.id ? C.accent + "33" : "transparent",
              border: tab === t.id ? `1px solid ${C.accent}44` : "1px solid transparent",
              borderRadius: 8, padding: "6px 14px",
              color: tab === t.id ? C.accentLight : C.textMuted,
              cursor: "pointer", fontSize: 13, fontWeight: 600,
              display: "flex", alignItems: "center", gap: 6,
            }}>
              <Icon d={t.icon} size={13} /> {t.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ maxWidth: 900, margin: "0 auto", padding: 24 }}>
        {tab === "chat"     && <ChatPanel projects={projects} />}
        {tab === "analyze"  && <AnalyzePanel projects={projects} />}
        {tab === "library"  && <StandardsLibrary standards={standards} loading={loadingStds} />}
        {tab === "projects" && (
          <ProjectManager projects={projects} standards={standards}
            onProjectCreated={loadProjects} onStandardPinned={loadProjects} />
        )}
        {tab === "upload"   && <UploadPanel onUploaded={loadStandards} />}
      </div>
    </div>
  );
}
