import { useLatestExplain } from './hooks/useLatestExplain';
import './App.css';

function BarGauge({ label, score, icon }: { label: string; score: number; icon: string }) {
  const level = score <= 3 ? 'low' : score <= 6 ? 'medium' : 'high';
  return (
    <div className="bar-row">
      <span className="bar-label">{icon} {label}</span>
      <div className="bar-gauge">
        <div
          className={`fill ${level}`}
          style={{ '--score': score } as React.CSSProperties}
        />
      </div>
      <span className={`bar-value ${level}`}>{score}/10</span>
    </div>
  );
}

function Badge({ text, type }: { text: string; type: 'pass' | 'fail' | 'revise' | 'neutral' }) {
  return <span className={`badge badge-${type}`}>{text}</span>;
}

function App() {
  const { data, loading } = useLatestExplain(800);

  if (loading || !data) {
    return (
      <div className="app dark empty-state">
        <div className="empty-card">
          <h1>🔍 LegacyLens Sidecar</h1>
          <p>Waiting for data…</p>
          <code>legacylens explain processFindForm --json --out dashboard/public/latest_explain.json</code>
        </div>
      </div>
    );
  }

  const { explanation, codebalance, critic, fidelity, verdict } = data;
  const verdictType = verdict === 'PASS' ? 'pass' : verdict === 'FAIL' ? 'fail' : 'revise';

  return (
    <div className="app dark">
      {/* ── Header ───────────────────────────────────────── */}
      <header className="header">
        <div className="header-left">
          <h1 className="logo">🔍 LegacyLens</h1>
          <span className="function-name">{data.function}</span>
        </div>
        <div className="header-right">
          <Badge text={verdict} type={verdictType} />
          {fidelity != null && (
            <Badge text={`Fidelity ${Math.round(fidelity * 100)}%`} type="neutral" />
          )}
          <Badge text={`Confidence ${data.confidence}%`} type="neutral" />
        </div>
      </header>

      <div className="grid">
        {/* ── Explanation Panel ──────────────────────────── */}
        <section className="card explanation-card">
          <h2>Explanation</h2>
          <div className="explanation-text">{explanation}</div>
          <div className="meta-row">
            <span>Iterations: {data.iterations}</span>
            <span>Source: {data.context_source}</span>
          </div>
        </section>

        {/* ── CodeBalance Panel ─────────────────────────── */}
        <section className="card codebalance-card">
          <h2>
            CodeBalance
            <span className={`grade grade-${codebalance.grade}`}>{codebalance.grade}</span>
          </h2>
          <BarGauge label="Energy" score={codebalance.energy} icon="⚡" />
          <BarGauge label="Debt" score={codebalance.debt} icon="🔧" />
          <BarGauge label="Safety" score={codebalance.safety} icon="🛡️" />
        </section>

        {/* ── Critic Panel ──────────────────────────────── */}
        {critic && (
          <section className="card critic-card">
            <h2>Critic Verdict</h2>
            <div className="critic-grid">
              <div className="critic-item">
                <span className="critic-label">Factual</span>
                <span className={critic.factual_pass ? 'pass-text' : 'fail-text'}>
                  {critic.factual_pass ? '✓ Pass' : '✗ Fail'}
                </span>
              </div>
              <div className="critic-item">
                <span className="critic-label">Completeness</span>
                <span>{critic.completeness_pct}%</span>
              </div>
              <div className="critic-item">
                <span className="critic-label">Risks flagged</span>
                <span>{critic.risks_mentioned?.length ?? 0}</span>
              </div>
            </div>
            {critic.issues && critic.issues.length > 0 && (
              <ul className="issues-list">
                {critic.issues.map((issue, i) => (
                  <li key={i}>{issue}</li>
                ))}
              </ul>
            )}
          </section>
        )}

        {/* ── Code Snippet Panel ────────────────────────── */}
        <section className="card code-card">
          <h2>Source Code</h2>
          <pre className="code-block"><code>{data.code_snippet}</code></pre>
          <div className="meta-row">
            <span>{data.file_path}</span>
          </div>
        </section>
      </div>

      <footer className="footer">
        Updated: {new Date(data.timestamp).toLocaleTimeString()}
      </footer>
    </div>
  );
}

export default App;
