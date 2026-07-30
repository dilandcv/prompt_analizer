import { useState } from "react";

const API = "";

function Header() {
  return (
    <header className="header">
      <div className="logo">
        <svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
        <h1>TOKEN <span className="gradient-text">ANALYZER</span></h1>
      </div>
      <p className="subtitle">ANALIZA &bull; TRADUCE &bull; OPTIMIZA &bull; RECOMIENDA</p>
    </header>
  );
}

function Tabs({ active, onTab }) {
  return (
    <nav className="tabs">
      <button className={`tab ${active === "prompt" ? "active" : ""}`} onClick={() => onTab("prompt")}>
        Caso 1 · Prompt Engineering
      </button>
      <button className={`tab ${active === "reviews" ? "active" : ""}`} onClick={() => onTab("reviews")}>
        Caso 2 · Reseñas Excel
      </button>
      <button className={`tab ${active === "citas" ? "active" : ""}`} onClick={() => onTab("citas")}>
        Caso 3 · Citas Médicas
      </button>
    </nav>
  );
}

function PromptTab({ onResult }) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [scan, setScan] = useState(false);

  async function analyze(e) {
    e.preventDefault();
    if (!text.trim()) return;
    setScan(true);
    setTimeout(() => setScan(false), 1500);
    setLoading(true);
    try {
      const form = new FormData();
      form.append("texto", text);
      const res = await fetch(`${API}/api/analyze`, { method: "POST", body: form });
      const data = await res.json();
      onResult(data);
    } catch (err) {
      onResult({ error: "Error conectando al backend: " + err.message });
    }
    setLoading(false);
  }

  return (
    <section style={{ marginBottom: "3rem" }}>
      <form onSubmit={analyze}>
        <div className="textarea-wrap">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Escribe o pega tu prompt aquí..."
            rows={6}
          />
          <div className={`scan-line ${scan ? "active" : ""}`} />
        </div>
        <div className="btn-wrap">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
            {loading ? "Analizando..." : "ANALIZAR PROMPT"}
          </button>
        </div>
      </form>
    </section>
  );
}

function ResultsSection({ data }) {
  if (data?.error) {
    return <div className="error-card"><span className="error-icon">!</span><p>{data.error}</p></div>;
  }
  const { original, idioma, tokens_orig, tokens_trad, traduccion, prompt, optimo, mejora, modelo } = data;

  return (
    <div className="fade-in">
      <div className="section-title"><h3>RESULTADOS</h3><div className="section-div" /></div>
      <div className="compare-grid">
        <div className="card">
          <div className="card-header">
            <span className={`badge ${idioma === "es" ? "es" : "en"}`}>{idioma?.toUpperCase()}</span>
            <h3>ORIGINAL</h3>
          </div>
          <p className="card-text">{original}</p>
          <div className="card-tokens">
            <span>{tokens_orig} tokens</span>
            <span>·</span>
            <span>{original?.split(" ").length} palabras</span>
          </div>
        </div>
        <div className="card">
          <div className="card-header">
            <span className={`badge ${idioma === "es" ? "en" : "es"}`}>{idioma === "es" ? "EN" : "ES"}</span>
            <h3>TRADUCCIÓN</h3>
          </div>
          <p className="card-text">{traduccion || "—"}</p>
          <div className="card-tokens">
            <span>{tokens_trad} tokens</span>
            <span>·</span>
            <span>{traduccion?.split(" ").filter(Boolean).length} palabras</span>
          </div>
        </div>
      </div>

      {mejora && (
        <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
          <div className="stat-card stat-highlight">
            <span className="stat-value">{mejora.ahorro}</span>
            <span className="stat-label">Tokens Ahorrados ({mejora.recomendacion?.toUpperCase()})</span>
          </div>
        </div>
      )}

      {/* Quality */}
      {prompt && <QualityCard prompt={prompt} />}

      {/* Improvement */}
      {!optimo && mejora && <ImprovementCard mejora={mejora} />}

      {/* Model Footer */}
      {modelo && (
        <div className="modelo-footer">
          <span>Modelo recomendado: </span>
          <span>{modelo.icono}</span>
          <strong>{modelo.modelo}</strong>
          <span style={{opacity:0.55}}>· Alternativa: {modelo.alternativo}</span>
        </div>
      )}
    </div>
  );
}

function QualityCard({ prompt }) {
  const { puntaje, nivel, detalles, fortalezas, debilidades, recomendaciones, evaluacion_ia } = prompt;
  return (
    <div className="card quality-card" style={{ marginBottom: "2.5rem" }}>
      <div className="card-header">
        <span className="badge">{nivel?.toUpperCase()?.replace("-", " ")}</span>
        <h3>CALIDAD DEL PROMPT <span className="score-pill">{puntaje}/100</span></h3>
      </div>
      {evaluacion_ia && (
        <div className="eval-source"><span className="eval-badge">QWEN 2.5</span></div>
      )}
      <div className="metrics-list">
        {detalles?.map(([nombre, puntos, comentario], i) => (
          <div className="metric-row" key={i}>
            <div className="metric-header">
              <span className="metric-name">{nombre}</span>
              <span className="metric-score">{puntos}</span>
            </div>
            <div className="metric-bar">
              <div className="metric-fill" style={{ width: `${Math.min(puntos * 4, 100)}%` }} />
            </div>
            <p className="metric-comment">{comentario}</p>
          </div>
        ))}
      </div>
      {(fortalezas?.length > 0 || debilidades?.length > 0 || recomendaciones?.length > 0) && (
        <div className="eval-extra">
          {fortalezas?.length > 0 && (
            <div className="eval-section strengths">
              <span className="eval-section-title">Fortalezas</span>
              <ul>{fortalezas.map((f, i) => <li key={i}>{f}</li>)}</ul>
            </div>
          )}
          {debilidades?.length > 0 && (
            <div className="eval-section weaknesses">
              <span className="eval-section-title">Debilidades</span>
              <ul>{debilidades.map((d, i) => <li key={i}>{d}</li>)}</ul>
            </div>
          )}
          {recomendaciones?.length > 0 && (
            <div className="eval-section recommendations">
              <span className="eval-section-title">Recomendaciones</span>
              <ul>{recomendaciones.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ImprovementCard({ mejora }) {
  const copy = () => {
    const text = mejora.recomendacion === "es" ? mejora.mejora_es : mejora.mejora_en;
    navigator.clipboard.writeText(text);
  };
  return (
    <div>
      <div className="section-title"><h3>PROMPT MEJORADO POR IA</h3><div className="section-div" /></div>
      <div className="card mejora-card" style={{ marginBottom: "2.5rem" }}>
        <div className="mejora-display" style={{ marginBottom: "0.75rem" }}>
          <div className="mejora-lang">
            <span className={`badge ${mejora.recomendacion}`}>{mejora.recomendacion?.toUpperCase()}</span>
            <span className="lang-tag">Versión optimizada</span>
          </div>
          <pre className="mejora-text">{mejora.recomendacion === "es" ? mejora.mejora_es : mejora.mejora_en}</pre>
        </div>
        <button className="btn-sm" onClick={copy}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
          Copiar prompt
        </button>
      </div>
    </div>
  );
}

/* ─── REVIEWS TAB ─── */

function ReviewsTab() {
  const [files, setFiles] = useState([]);
  const [optimizar, setOptimizar] = useState(true);
  const [rapido, setRapido] = useState(true);
  const [columna, setColumna] = useState("");
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 15;

  async function processReviews(e) {
    e.preventDefault();
    if (files.length === 0) return setError("Selecciona al menos un archivo.");
    setLoading(true); setError(""); setData(null);
    try {
      const form = new FormData();
      files.forEach((f) => form.append("archivos", f));
      form.append("columna", columna);
      form.append("optimizar", optimizar ? "true" : "false");
      form.append("rapido", rapido ? "true" : "false");
      const res = await fetch(`${API}/api/reviews`, { method: "POST", body: form });
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail || "Error"); }
      setData(await res.json());
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }

  function exportFile(fmt) {
    if (!data?.resultados) return;
    fetch(`${API}/api/reviews/export/${fmt}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resultados: data.resultados }),
    }).then((r) => r.blob()).then((b) => {
      const url = URL.createObjectURL(b);
      const a = document.createElement("a");
      a.href = url; a.download = `reviews.${fmt === "xlsx" ? "xlsx" : fmt}`;
      a.click(); URL.revokeObjectURL(url);
    });
  }

  const totalPages = data ? Math.ceil(data.resultados.length / pageSize) : 0;
  const pageData = data ? data.resultados.slice(page * pageSize, (page + 1) * pageSize) : [];

  return (
    <div>
      <section style={{ marginBottom: "3rem" }}>
        <form onSubmit={processReviews}>
          <div className="input-row">
            <div className="textarea-wrap">
              <textarea placeholder="Opcional: escribe o pega reseñas (una por línea)..."
                        rows={3} style={{ minHeight: 90 }}
                        onChange={(e) => { if (e.target.value.trim()) setFiles([]); }} />
            </div>
            <label className="attach-btn" title="Adjuntar archivos">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
              <input type="file" accept=".xlsx,.csv,.pdf,.txt" multiple
                     onChange={(e) => setFiles(Array.from(e.target.files))}
                     style={{ display: "none" }} />
            </label>
          </div>
          {files.length > 0 && (
            <p style={{ fontSize: "0.72rem", color: "var(--accent)", marginTop: "0.4rem" }}>
              {files.map((f) => f.name).join(", ")}
            </p>
          )}
          {data?.columnas_disponibles?.length > 0 && (
            <div style={{ marginBottom: "0.75rem", marginTop: "0.75rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Columna:</span>
              <select value={columna} onChange={(e) => setColumna(e.target.value)}
                      style={{ padding: "0.4rem 0.7rem", background: "var(--bg-input)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-xs)", color: "var(--text-primary)", fontSize: "0.8rem" }}>
                <option value="">Auto-detectar</option>
                {data.columnas_disponibles.map((c) => <option key={c}>{c}</option>)}
              </select>
            </div>
          )}
          <div className="toggle-wrapper">
            <span className="toggle-label">Optimizar Tokens</span>
            <label className="toggle-switch">
              <input type="checkbox" checked={optimizar} onChange={(e) => setOptimizar(e.target.checked)} />
              <span className="toggle-slider" />
            </label>
          </div>
          <div className="toggle-wrapper">
            <span className="toggle-label">Modo Rápido (solo heurística)</span>
            <label className="toggle-switch">
              <input type="checkbox" checked={rapido} onChange={(e) => setRapido(e.target.checked)} />
              <span className="toggle-slider" />
            </label>
          </div>
          <div className="btn-wrap">
            <button type="submit" className="btn btn-primary" disabled={loading}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              {loading ? "Procesando..." : "PROCESAR RESEÑAS"}
            </button>
          </div>
        </form>
      </section>

      {error && <div className="error-card"><span className="error-icon">!</span><p>{error}</p></div>}

      {data && (
        <div className="fade-in">
          {/* Stats */}
          <div className="section-title"><h3>ESTADÍSTICAS</h3><div className="section-div" /></div>
          <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
            <div className="stat-card"><span className="stat-value">{data.stats.total_resenas}</span><span className="stat-label">Reseñas</span></div>
            <div className="stat-card"><span className="stat-value">{data.stats.total_tokens_es?.toLocaleString()}</span><span className="stat-label">Tokens (ES)</span></div>
            <div className="stat-card"><span className="stat-value">{data.stats.total_tokens_en?.toLocaleString()}</span><span className="stat-label">Tokens ({data.optimizar ? "EN" : "ES"})</span></div>
            <div className="stat-card"><span className="stat-value">{data.stats.promedio_es} / {data.stats.promedio_en}</span><span className="stat-label">Promedio (ES/EN)</span></div>
          </div>

          {/* Econ Simulation */}
          <div className="section-title"><h3>SIMULACIÓN ECONÓMICA</h3><div className="section-div" /></div>
          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>10.000 reseñas/día · 30 días · $2.50 USD / 1M tokens</p>
          <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
            <div className="stat-card"><span className="stat-value">${data.stats.costo_mensual_es?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span><span className="stat-label">Costo Mensual (ES)</span></div>
            <div className="stat-card"><span className="stat-value">${data.stats.costo_mensual_en?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span><span className="stat-label">Costo Mensual ({data.optimizar ? "EN" : "ES"})</span></div>
            <div className="stat-card stat-highlight"><span className="stat-value">${data.stats.ahorro?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span><span className="stat-label">Ahorro ({data.stats.pct_ahorro}%)</span></div>
          </div>

          {/* Table */}
          <div className="section-title"><h3>RESULTADOS</h3><div className="section-div" /></div>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
            <button className="btn-sm" onClick={() => exportFile("csv")}>CSV</button>
            <button className="btn-sm" onClick={() => exportFile("xlsx")}>Excel</button>
            <button className="btn-sm" onClick={() => exportFile("json")}>JSON</button>
          </div>

          <div style={{ overflowX: "auto", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", marginBottom: "1rem" }}>
            <table className="batch-table">
              <thead><tr>
                <th>#</th><th>Reseña</th><th>Tokens ES</th><th>Tokens EN</th><th>Costo</th><th>Error</th><th>Severity</th><th>JSON</th><th>Estado</th>
              </tr></thead>
              <tbody>
                {pageData.map((r, i) => {
                  const c = r.clasificacion || {};
                  return (
                    <React.Fragment key={i}>
                      <tr>
                        <td>{page * pageSize + i + 1}</td>
                        <td className="review-cell" title={r.original}>{r.original?.slice(0, 70)}{r.original?.length > 70 ? "…" : ""}</td>
                        <td>{r.tokens_es}</td><td>{r.tokens_en}</td>
                        <td>${r.costo?.toFixed(4)}</td>
                        <td>{c.error_type || "-"}</td>
                        <td>{c.severity || "-"}</td>
                        <td><button className="json-toggle" onClick={(e) => { const tr = e.target.closest("tr").nextElementSibling; tr.style.display = tr.style.display === "none" ? "" : "none"; e.target.textContent = tr.style.display === "none" ? "Ver" : "Ocultar"; }}>Ver</button></td>
                        <td><span style={{ padding: "0.1rem 0.5rem", borderRadius: "6px", fontSize: "0.6rem", fontWeight: 600, background: "var(--success-soft)", color: "var(--success)" }}>OK</span></td>
                      </tr>
                      <tr className="json-row" style={{ display: "none" }}>
                        <td colSpan={9}><pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>{JSON.stringify(c, null, 2)}</pre></td>
                      </tr>
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <button disabled={page === 0} onClick={() => setPage(0)}>&laquo;</button>
            <button disabled={page === 0} onClick={() => setPage(page - 1)}>&lsaquo;</button>
            <span>{page + 1} / {totalPages}</span>
            <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>&rsaquo;</button>
            <button disabled={page >= totalPages - 1} onClick={() => setPage(totalPages - 1)}>&raquo;</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── CITAS TAB ─── */

function CitasTab() {
  const [files, setFiles] = useState([]);
  const [carpeta, setCarpeta] = useState("");
  const [modo, setModo] = useState("archivo");
  const [optimizar, setOptimizar] = useState(true);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const pageSize = 15;

  async function processCitas(e) {
    e.preventDefault();
    setError(""); setData(null);

    try {
      if (modo === "archivo") {
        if (files.length === 0) {
          setError("Selecciona al menos un archivo.");
          return;
        }
        setLoading(true);
        const form = new FormData();
        files.forEach((f) => form.append("archivos", f));
        form.append("optimizar_tokens", optimizar ? "true" : "false");
        const res = await fetch(`${API}/api/citas/analyze`, { method: "POST", body: form });
        if (!res.ok) { const d = await res.json(); throw new Error(d.detail || "Error"); }
        setData(await res.json());
      } else {
        if (!carpeta.trim()) {
          setError("Ingresa una ruta de carpeta.");
          return;
        }
        setLoading(true);
        const form = new FormData();
        form.append("carpeta", carpeta);
        form.append("optimizar_tokens", optimizar ? "true" : "false");
        const res = await fetch(`${API}/api/citas/analyze/folder`, { method: "POST", body: form });
        if (!res.ok) { const d = await res.json(); throw new Error(d.detail || "Error"); }
        setData(await res.json());
      }
    } catch (err) {
      setError(err.message);
      setData(null);
    }
    setLoading(false);
  }

  function exportFile(fmt) {
    if (!data?.resultados) return;
    fetch(`${API}/api/citas/export/${fmt}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ resultados: data.resultados }),
    }).then((r) => r.blob()).then((b) => {
      const url = URL.createObjectURL(b);
      const a = document.createElement("a");
      a.href = url; a.download = `citas.${fmt === "xlsx" ? "xlsx" : fmt}`;
      a.click(); URL.revokeObjectURL(url);
    });
  }

  const totalPages = data ? Math.ceil(data.resultados.length / pageSize) : 0;
  const pageData = data ? data.resultados.slice(page * pageSize, (page + 1) * pageSize) : [];

  return (
    <div>
      <section style={{ marginBottom: "3rem" }}>
        <form onSubmit={processCitas}>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
            <button type="button" className={`btn-sm ${modo === "archivo" ? "btn-primary" : ""}`}
                    onClick={() => setModo("archivo")} style={{ borderRadius: "var(--radius-xs)", fontSize: "0.75rem", padding: "0.4rem 1rem" }}>
              Archivo
            </button>
            <button type="button" className={`btn-sm ${modo === "carpeta" ? "btn-primary" : ""}`}
                    onClick={() => setModo("carpeta")} style={{ borderRadius: "var(--radius-xs)", fontSize: "0.75rem", padding: "0.4rem 1rem" }}>
              Carpeta
            </button>
          </div>

          {modo === "archivo" ? (
            <div className="input-row">
              <label className="attach-btn" title="Adjuntar archivos Excel" style={{ width: "100%", justifyContent: "center" }}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
                <span style={{ marginLeft: "0.5rem", fontSize: "0.8rem" }}>
                  {files.length > 0 ? `${files.length} archivo(s)` : "Seleccionar archivos Excel"}
                </span>
                <input type="file" accept=".xlsx" multiple
                       onChange={(e) => setFiles(Array.from(e.target.files))}
                       style={{ display: "none" }} />
              </label>
            </div>
          ) : (
            <div className="textarea-wrap">
              <input
                type="text"
                value={carpeta}
                onChange={(e) => setCarpeta(e.target.value)}
                placeholder="Ruta de carpeta con archivos .xlsx..."
                style={{ width: "100%", padding: "0.75rem", background: "var(--bg-input)", border: "1px solid var(--border-default)", borderRadius: "var(--radius-xs)", color: "var(--text-primary)", fontSize: "0.85rem" }}
              />
            </div>
          )}

          {modo === "archivo" && files.length > 0 && (
            <p style={{ fontSize: "0.72rem", color: "var(--accent)", marginTop: "0.4rem" }}>
              {files.map((f) => f.name).join(", ")}
            </p>
          )}

          {data?.columnas_disponibles?.length > 0 && (
            <p style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "0.4rem" }}>
              Columnas: {data.columnas_disponibles.join(", ")}
            </p>
          )}

          <div className="toggle-wrapper">
            <span className="toggle-label">Optimizar Tokens (traducir y comparar ES vs EN)</span>
            <label className="toggle-switch">
              <input type="checkbox" checked={optimizar} onChange={(e) => setOptimizar(e.target.checked)} />
              <span className="toggle-slider" />
            </label>
          </div>

          <div className="btn-wrap">
            <button type="submit" className="btn btn-primary" disabled={loading}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>
              {loading ? "Procesando..." : "PROCESAR CITAS"}
            </button>
          </div>
        </form>
      </section>

      {error && <div className="error-card"><span className="error-icon">!</span><p>{error}</p></div>}

      {data && (
        <div className="fade-in">
          {/* Stats */}
          <div className="section-title"><h3>RESUMEN DE OPTIMIZACIÓN</h3><div className="section-div" /></div>
          <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
            <div className="stat-card"><span className="stat-value">{data.stats.total_registros}</span><span className="stat-label">Registros</span></div>
            <div className="stat-card"><span className="stat-value">{data.stats.tokens_originales?.toLocaleString()}</span><span className="stat-label">Tokens Originales</span></div>
            <div className="stat-card"><span className="stat-value">{data.stats.tokens_optimizados?.toLocaleString()}</span><span className="stat-label">Tokens Optimizados</span></div>
            <div className="stat-card stat-highlight"><span className="stat-value">{data.stats.tokens_ahorrados?.toLocaleString()} ({data.stats.porcentaje_reduccion}%)</span><span className="stat-label">Ahorro Total</span></div>
          </div>

          {/* Econ Simulation */}
          <div className="section-title"><h3>SIMULACIÓN ECONÓMICA</h3><div className="section-div" /></div>
          <p style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>15.000 citas/día · 30 días · $2.50 USD / 1M tokens</p>
          <div className="stats-grid" style={{ marginBottom: "1.5rem" }}>
            <div className="stat-card"><span className="stat-value">${data.stats.costo_mensual_original?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span><span className="stat-label">Costo Mensual (Original)</span></div>
            <div className="stat-card"><span className="stat-value">${data.stats.costo_mensual_optimizado?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span><span className="stat-label">Costo Mensual (Optimizado)</span></div>
            <div className="stat-card stat-highlight"><span className="stat-value">${data.stats.ahorro_mensual?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span><span className="stat-label">Ahorro Mensual</span></div>
          </div>

          {/* Table */}
          <div className="section-title"><h3>RESULTADOS</h3><div className="section-div" /></div>
          <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem", flexWrap: "wrap" }}>
            <button className="btn-sm" onClick={() => exportFile("csv")}>CSV</button>
            <button className="btn-sm" onClick={() => exportFile("xlsx")}>Excel</button>
            <button className="btn-sm" onClick={() => exportFile("json")}>JSON</button>
          </div>

          <div style={{ overflowX: "auto", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-sm)", marginBottom: "1rem" }}>
            <table className="batch-table">
              <thead><tr>
                <th>#</th><th>ID</th><th>Original</th><th>Traducción</th><th>Optimizado</th><th>Idioma</th><th>Tok Orig</th><th>Tok Trad</th><th>Tok Opt</th><th>Ahorro</th><th>%</th>
              </tr></thead>
              <tbody>
                {pageData.map((r, i) => (
                  <tr key={i}>
                    <td>{page * pageSize + i + 1}</td>
                    <td>{r.paciente_id || "-"}</td>
                    <td className="review-cell" title={r.original}>{r.original?.slice(0, 45)}{r.original?.length > 45 ? "…" : ""}</td>
                    <td className="review-cell" title={r.traduccion}>{r.traduccion?.slice(0, 45)}{r.traduccion?.length > 45 ? "…" : ""}</td>
                    <td className="review-cell" title={r.texto_optimizado}>{r.texto_optimizado?.slice(0, 45)}{r.texto_optimizado?.length > 45 ? "…" : ""}</td>
                    <td><span className={`badge ${r.idioma === "es" ? "es" : "en"}`}>{r.idioma?.toUpperCase()}</span></td>
                    <td>{r.tokens_original}</td>
                    <td>{r.tokens_traduccion}</td>
                    <td>{r.tokens_optimizado}</td>
                    <td>{r.tokens_ahorrados}</td>
                    <td><span style={{ color: r.porcentaje_reduccion > 0 ? "var(--success)" : "var(--text-muted)" }}>{r.porcentaje_reduccion}%</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="pagination">
            <button disabled={page === 0} onClick={() => setPage(0)}>&laquo;</button>
            <button disabled={page === 0} onClick={() => setPage(page - 1)}>&lsaquo;</button>
            <span>{page + 1} / {totalPages}</span>
            <button disabled={page >= totalPages - 1} onClick={() => setPage(page + 1)}>&rsaquo;</button>
            <button disabled={page >= totalPages - 1} onClick={() => setPage(totalPages - 1)}>&raquo;</button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── APP ─── */

export default function App() {
  const [tab, setTab] = useState("prompt");
  const [result, setResult] = useState(null);

  return (
    <>
      <div className="bg-layer" />
      <div className="container">
        <Header />
        <Tabs active={tab} onTab={(t) => { setTab(t); setResult(null); }} />

        {tab === "prompt" && (
          <>
            <PromptTab onResult={setResult} />
            {result && <ResultsSection data={result} />}
          </>
        )}
        {tab === "reviews" && <ReviewsTab />}
        {tab === "citas" && <CitasTab />}
      </div>
    </>
  );
}

import React from "react";
