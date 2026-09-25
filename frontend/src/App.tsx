import { useCallback, useEffect, useRef, useState } from 'react';
import { ImpactGraph } from './ImpactGraph';
import type { AnalysisReport, AnalysisStatus, TestResult } from './types';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { detail?: string } | null;
    throw new Error(body?.detail || `CodeTwin API returned ${response.status}`);
  }
  return response.json() as Promise<T>;
}

const statusCopy: Record<AnalysisStatus, { label: string; detail: string; icon: string }> = {
  awaiting_bob_review: {
    label: 'Awaiting IBM Bob',
    detail: 'The deterministic prediction is ready for semantic review.',
    icon: '◌',
  },
  awaiting_tests: {
    label: 'Ready for tests',
    detail: 'Bob has reviewed the predicted impact. Run the targeted tests.',
    icon: '◷',
  },
  safe_to_merge: {
    label: 'Safe to Merge',
    detail: 'Bob review and all targeted validation checks passed.',
    icon: '✓',
  },
  regression_detected: {
    label: 'Regression detected',
    detail: 'At least one targeted test failed. Fix the change, then revalidate.',
    icon: '!',
  },
  possible_impact_unresolved: {
    label: 'Possible impact unresolved',
    detail: 'Tests passed, but Bob left possible impact that still needs review.',
    icon: '?',
  },
  analysis_errors: {
    label: 'Analysis needs attention',
    detail: 'Python parse errors prevent a safe merge result.',
    icon: '!',
  },
  test_execution_error: {
    label: 'Test execution error',
    detail: 'CodeTwin could not complete every targeted test.',
    icon: '!',
  },
  no_targeted_tests: {
    label: 'No targeted tests found',
    detail: 'No tests were identified, so CodeTwin cannot mark this safe to merge.',
    icon: '—',
  },
};

function Icon({ name }: { name: 'check' | 'arrow' | 'copy' | 'refresh' | 'code' | 'test' | 'shield' | 'external' }) {
  const common = { fill: 'none', stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const };
  switch (name) {
    case 'check': return <svg viewBox="0 0 24 24" aria-hidden="true"><path {...common} d="m5 12 4 4L19 6" /></svg>;
    case 'arrow': return <svg viewBox="0 0 24 24" aria-hidden="true"><path {...common} d="M5 12h14m-6-6 6 6-6 6" /></svg>;
    case 'copy': return <svg viewBox="0 0 24 24" aria-hidden="true"><rect {...common} x="8" y="8" width="12" height="12" rx="2" /><path {...common} d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3" /></svg>;
    case 'refresh': return <svg viewBox="0 0 24 24" aria-hidden="true"><path {...common} d="M20 11a8 8 0 0 0-14.9-3M4 4v4h4m-4 5a8 8 0 0 0 14.9 3M20 20v-4h-4" /></svg>;
    case 'code': return <svg viewBox="0 0 24 24" aria-hidden="true"><path {...common} d="m8 8-4 4 4 4m8-8 4 4-4 4m-3-11-2 14" /></svg>;
    case 'test': return <svg viewBox="0 0 24 24" aria-hidden="true"><path {...common} d="M9 3h6m-5 0v6l-5.2 8.2A2.5 2.5 0 0 0 6.9 21h10.2a2.5 2.5 0 0 0 2.1-3.8L14 9V3m-6 11h8" /></svg>;
    case 'shield': return <svg viewBox="0 0 24 24" aria-hidden="true"><path {...common} d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path {...common} d="m9 12 2 2 4-4" /></svg>;
    case 'external': return <svg viewBox="0 0 24 24" aria-hidden="true"><path {...common} d="M14 4h6v6m-11 5L20 4" /><path {...common} d="M19 13v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h6" /></svg>;
  }
}

function StatCard({ label, value, meta, tone }: { label: string; value: string | number; meta: string; tone?: string }) {
  return (
    <div className="stat-card">
      <span className="stat-label">{label}</span>
      <strong className={tone ? `stat-value ${tone}` : 'stat-value'}>{value}</strong>
      <span className="stat-meta">{meta}</span>
    </div>
  );
}

function shortPath(path: string) {
  return path.replace(/^app\//, '').replace(/^tests\//, 'tests / ');
}

function App() {
  const [report, setReport] = useState<AnalysisReport | null>(null);
  const [busy, setBusy] = useState<'demo' | 'tests' | 'revalidate' | null>(null);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [error, setError] = useState('');
  const [copied, setCopied] = useState(false);
  const polling = useRef<number | undefined>(undefined);

  useEffect(() => {
    let active = true;
    apiRequest<{ status: string }>('/health')
      .then(() => active && setApiOnline(true))
      .catch(() => active && setApiOnline(false));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!report || !['awaiting_bob_review', 'awaiting_tests'].includes(report.status)) return;
    let active = true;
    const refresh = async () => {
      try {
        const updated = await apiRequest<AnalysisReport>(`/analyses/${report.analysis_id}`);
        if (active) setReport(updated);
      } catch {
        // Preserve the last valid report while the local API is restarting.
      }
    };
    polling.current = window.setInterval(refresh, 1800);
    return () => {
      active = false;
      if (polling.current !== undefined) window.clearInterval(polling.current);
    };
  }, [report?.analysis_id, report?.status]);

  const startDemo = useCallback(async () => {
    setBusy('demo');
    setError('');
    setCopied(false);
    try {
      const created = await apiRequest<AnalysisReport>('/demo/payment-regression', { method: 'POST' });
      setReport(created);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not start the demo analysis.');
    } finally {
      setBusy(null);
    }
  }, []);

  const runTests = useCallback(async () => {
    if (!report) return;
    setBusy('tests');
    setError('');
    try {
      const updated = await apiRequest<AnalysisReport>(`/analyses/${report.analysis_id}/run-tests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      setReport(updated);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not run targeted tests.');
    } finally {
      setBusy(null);
    }
  }, [report]);

  const simulateFixAndRevalidate = useCallback(async () => {
    if (!report) return;
    setBusy('revalidate');
    setError('');
    setCopied(false);
    try {
      const corrected = await apiRequest<AnalysisReport>(`/analyses/${report.analysis_id}/demo-fix`, {
        method: 'POST',
      });
      setReport(corrected);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Could not create the corrected demo revision.');
    } finally {
      setBusy(null);
    }
  }, [report]);

  const copyAnalysisId = useCallback(async () => {
    if (!report) return;
    try {
      await navigator.clipboard.writeText(report.analysis_id);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2200);
    } catch {
      setError('Clipboard access is unavailable. Copy the analysis ID shown here.');
    }
  }, [report]);

  const status = report ? statusCopy[report.status] : null;
  const bobReview = report?.bob_review;
  const testResults = report?.test_results;
  const testFiles = testResults?.targeted_tests ?? report?.predicted_impact.tests ?? [];
  const fixedDemo = report?.demo_scenario === 'payment_amount_regression_fixed';

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="CodeTwin home">
          <span className="brand-mark"><span /><span /><span /></span>
          <span>CodeTwin</span>
        </a>
        <div className="topbar-right">
          <span className="local-badge"><span /> HACKATHON DEMO</span>
          <span className={`api-indicator ${apiOnline === false ? 'offline' : ''}`}>
            <span className="api-dot" />
            {apiOnline === null ? 'Connecting' : apiOnline ? 'API connected' : 'API offline'}
          </span>
          <div className="avatar" title="Local developer workspace">CT</div>
        </div>
      </header>

      <main id="top" className="page-content">
        <section className="page-heading">
          <div>
            <div className="eyebrow"><span className="eyebrow-line" /> CHANGE INTELLIGENCE</div>
            <h1>Know what your change will touch.</h1>
            <p>Predict impact, validate it with IBM Bob, and run the tests that matter before merge.</p>
          </div>
          {report && (
            <button className="button button-secondary new-analysis" onClick={startDemo} disabled={busy !== null}>
              <Icon name="refresh" /> New demo analysis
            </button>
          )}
        </section>

        {!report ? (
          <section className="start-card">
            <div className="start-copy">
              <span className="start-icon"><Icon name="code" /></span>
              <div className="eyebrow">READY TO ANALYZE</div>
              <h2>See a payment regression before it reaches production.</h2>
              <p>
                Load the synthetic shop change. CodeTwin maps the downstream files and tests,
                IBM Bob reviews semantic impact, then targeted checks decide the merge status.
              </p>
              <button className="button button-primary start-button" onClick={startDemo} disabled={busy !== null || apiOnline === false}>
                {busy === 'demo' ? <span className="spinner" /> : <Icon name="arrow" />}
                {busy === 'demo' ? 'Building impact graph…' : 'Analyze payment regression'}
              </button>
              {apiOnline === false && <span className="inline-note">Start the FastAPI service from the backend folder to begin.</span>}
            </div>
            <div className="start-preview" aria-hidden="true">
              <div className="preview-window">
                <div className="preview-title"><span /><span /><span /> payment_service.py</div>
                <div className="preview-code">
                  <div><span>18</span><code>def capture_payment(order_id, amount_cents):</code></div>
                  <div className="code-removed"><span>19</span><code>- amount_cents=amount_cents</code></div>
                  <div className="code-added"><span>19</span><code>+ amount_cents=amount_cents // 100</code></div>
                  <div><span>20</span><code>return create_payment(...)</code></div>
                </div>
                <div className="preview-alert"><span className="alert-mark">!</span><span>Payment amount mismatch detected</span></div>
              </div>
              <div className="preview-orbit orbit-one" />
              <div className="preview-orbit orbit-two" />
            </div>
            <div className="workflow-strip">
              <div className="workflow-step"><span className="step-number">01</span><span>Deterministic<br />impact graph</span></div>
              <span className="workflow-connector" />
              <div className="workflow-step"><span className="step-number">02</span><span>IBM Bob<br />semantic review</span></div>
              <span className="workflow-connector" />
              <div className="workflow-step"><span className="step-number">03</span><span>Targeted<br />test validation</span></div>
              <span className="workflow-connector" />
              <div className="workflow-step"><span className="step-number">04</span><span>Evidence-based<br />merge status</span></div>
            </div>
          </section>
        ) : (
          <>
            <section className={`analysis-banner ${report.safe_to_merge ? 'banner-safe' : report.status === 'regression_detected' ? 'banner-risk' : ''}`}>
              <div className="banner-main">
                <div className={`banner-icon ${report.safe_to_merge ? 'safe' : report.status === 'regression_detected' ? 'risk' : ''}`}>
                  {report.safe_to_merge ? <Icon name="check" /> : status?.icon}
                </div>
                <div>
                  <span className="banner-label">MERGE READINESS</span>
                  <h2>{status?.label}</h2>
                  <p>{status?.detail}</p>
                </div>
              </div>
              <div className="analysis-id-box">
                <span>ANALYSIS ID</span>
                <code>{report.analysis_id}</code>
                <button onClick={copyAnalysisId} title="Copy analysis ID"><Icon name="copy" />{copied ? 'Copied' : 'Copy'}</button>
              </div>
            </section>

            <section className="change-summary card-surface">
              <div className="change-file-icon"><Icon name="code" /></div>
              <div className="change-file-info">
                <span className="section-kicker">PROPOSED CHANGE <span className="scenario-label">{fixedDemo ? 'PAYMENT REGRESSION FIX' : 'PAYMENT AMOUNT REGRESSION'}</span></span>
                <strong>{report.changed_files[0]}</strong>
                <span className="change-description">
                  {fixedDemo ? 'The corrected payment flow preserves the amount in cents.' : 'Currency units are divided by 100 before the captured payment is stored.'}
                </span>
              </div>
              <div className="change-diff" aria-label="Payment amount source change">
                <code className="diff-before">{fixedDemo ? 'amount_cents=amount_cents // 100' : 'amount_cents=amount_cents'}</code>
                <span>→</span>
                <code className="diff-after">{fixedDemo ? 'amount_cents=amount_cents' : 'amount_cents=amount_cents // 100'}</code>
              </div>
            </section>

            <section className="stats-grid" aria-label="Impact summary">
              <StatCard label="PREDICTED FILES" value={report.predicted_impact.files.length} meta="including downstream dependents" tone="blue" />
              <StatCard label="API SURFACE" value={report.predicted_impact.api_files.length} meta="routes and entry points" tone="violet" />
              <StatCard label="TARGETED TESTS" value={report.predicted_impact.tests.length} meta="selected by the dependency graph" tone="teal" />
              <StatCard label="COMPONENTS" value={report.predicted_impact.components.length} meta="repository areas in scope" tone="orange" />
            </section>

            <section className="main-grid">
              <div className="panel graph-panel">
                <div className="panel-heading">
                  <div>
                    <div className="section-kicker">DETERMINISTIC ANALYSIS</div>
                    <h2>Impact graph</h2>
                  </div>
                  <span className="method-badge"><span /> PYTHON AST</span>
                </div>
                <p className="panel-description">Imports are traced downstream from the changed payment service.</p>
                <ImpactGraph report={report} />
                <div className="graph-legend">
                  <span><i className="legend-dot changed" /> Changed</span>
                  <span><i className="legend-dot predicted" /> Predicted impact</span>
                  <span><i className="legend-dot confirmed" /> Bob confirmed</span>
                  <span><i className="legend-dot possible" /> Possible impact</span>
                </div>
                {report.parse_errors.length > 0 && (
                  <div className="parse-errors">
                    {report.parse_errors.map((item) => <div key={item.file}><strong>{item.file}</strong>: {item.message}</div>)}
                  </div>
                )}
              </div>

              <aside className="panel bob-panel">
                <div className="panel-heading">
                  <div>
                    <div className="section-kicker">SEMANTIC VALIDATION</div>
                    <h2>IBM Bob review</h2>
                  </div>
                  <span className={`bob-mark ${bobReview ? 'complete' : ''}`}>b</span>
                </div>
                {!bobReview ? (
                  <>
                    <div className="bob-waiting"><span className="bob-pulse" /><div><strong>Waiting for Bob</strong><span>Give Bob the analysis ID to review this snapshot.</span></div></div>
                    <div className="bob-steps">
                      <div><span>1</span><p>Open this workspace in IBM Bob.</p></div>
                      <div><span>2</span><p>Ask Bob: <code>Review CodeTwin analysis {report.analysis_id}</code></p></div>
                      <div><span>3</span><p>Bob inspects the change and records its file classifications here.</p></div>
                    </div>
                    <div className="bob-config-note"><span>↗</span><p>Project MCP tools are configured in <code>.bob/mcp.json</code>.</p></div>
                  </>
                ) : (
                  <>
                    <div className="bob-complete-row"><span className="complete-check"><Icon name="check" /></span><div><strong>Semantic review complete</strong><span>IBM Bob classified the repository snapshot.</span></div></div>
                    <div className="bob-counts">
                      <div><strong className="count-confirmed">{bobReview.bob_confirmed_impact.length}</strong><span>Confirmed</span></div>
                      <div><strong className="count-possible">{bobReview.possible_impact.length}</strong><span>Possible</span></div>
                      <div><strong className="count-unaffected">{bobReview.not_affected.length}</strong><span>Not affected</span></div>
                    </div>
                    <div className="bob-rationale"><span>BOB'S REVIEW NOTE</span><p>{bobReview.rationale}</p></div>
                    {report.status === 'awaiting_tests' && <div className="bob-next">Review recorded · Ready for targeted tests</div>}
                  </>
                )}
              </aside>
            </section>

            <section className="bottom-grid">
              <div className="panel validation-panel">
                <div className="panel-heading">
                  <div>
                    <div className="section-kicker">EXECUTION EVIDENCE</div>
                    <h2>Targeted validation</h2>
                  </div>
                  <span className={`validation-state ${testResults?.passed ? 'passed' : testResults?.status === 'failed' ? 'failed' : ''}`}>
                    {testResults?.status === 'not_run' ? 'NOT RUN' : testResults?.status?.replaceAll('_', ' ').toUpperCase()}
                  </span>
                </div>
                <p className="panel-description">Only the tests selected by the impact graph are executed.</p>
                {testFiles.length > 0 ? (
                  <div className="test-list">
                    {testFiles.map((testFile) => {
                      const result = testResults?.results?.find((item: TestResult) => item.file === testFile);
                      return (
                        <div className="test-row" key={testFile}>
                          <span className={`test-state-icon ${result?.status ?? 'pending'}`}>
                            {result?.status === 'passed' ? <Icon name="check" /> : result?.status === 'failed' || result?.status === 'error' ? '!' : '·'}
                          </span>
                          <code>{testFile}</code>
                          <span className={`test-result-label ${result?.status ?? 'pending'}`}>{result?.status ?? 'pending'}</span>
                        </div>
                      );
                    })}
                  </div>
                ) : <div className="empty-tests">No tests are connected to this change.</div>}
                {testResults?.results?.some((item) => item.output) && (
                  <details className="test-output-details" open={testResults.status === 'failed'}>
                    <summary>Test output</summary>
                    <div className="test-output">
                      {testResults.results.map((result) => result.output && (
                        <pre key={result.file}><span>{result.file}</span>{'\n'}{result.output}</pre>
                      ))}
                    </div>
                  </details>
                )}
                <button
                  className={`button ${testResults?.passed ? 'button-secondary' : 'button-primary'} run-tests-button`}
                  onClick={runTests}
                  disabled={!bobReview || busy !== null || report.status !== 'awaiting_tests'}
                >
                  {busy === 'tests' ? <span className="spinner" /> : <Icon name="test" />}
                  {busy === 'tests' ? 'Running targeted tests…' : report.status === 'regression_detected' ? 'Regression detected' : 'Run targeted tests'}
                </button>
                {!bobReview && <span className="button-hint">Complete the IBM Bob review before running tests.</span>}
                {bobReview?.possible_impact.length ? <span className="button-hint">Resolve possible impact before Safe to Merge can be reported.</span> : null}
                {report.status === 'regression_detected' && report.demo_scenario === 'payment_amount_regression' && (
                  <div className="revalidation-action">
                    <strong>Fix the detected payment regression</strong>
                    <p>Start a corrected snapshot from this failed run. IBM Bob reviews the new revision before its tests can pass the merge gate.</p>
                    <button className="button button-secondary" onClick={simulateFixAndRevalidate} disabled={busy !== null}>
                      {busy === 'revalidate' ? <span className="spinner" /> : <Icon name="refresh" />}
                      {busy === 'revalidate' ? 'Creating corrected revision…' : 'Simulate fix & revalidate'}
                    </button>
                  </div>
                )}
                {fixedDemo && report.parent_analysis_id && (
                  <span className="button-hint">Corrected revision of analysis {report.parent_analysis_id.slice(0, 12)} · Bob review required again.</span>
                )}
              </div>

              <div className="panel classification-panel">
                <div className="panel-heading">
                  <div>
                    <div className="section-kicker">FILE CLASSIFICATION</div>
                    <h2>Impact assessment</h2>
                  </div>
                  <span className="classification-total">{report.predicted_impact.files.length + report.not_affected.length} files</span>
                </div>
                <div className="classification-group">
                  <div className="classification-title"><span className="classification-marker marker-predicted" /><strong>Predicted impact</strong><span>{report.predicted_impact.files.length}</span></div>
                  <div className="file-chips">
                    {report.predicted_impact.files.map((path) => <code key={path} title={path}>{shortPath(path)}</code>)}
                  </div>
                </div>
                {bobReview && (
                  <>
                    <div className="classification-group">
                      <div className="classification-title"><span className="classification-marker marker-confirmed" /><strong>Bob-confirmed impact</strong><span>{bobReview.bob_confirmed_impact.length}</span></div>
                      <div className="file-chips">
                        {bobReview.bob_confirmed_impact.map((path) => <code key={path} title={path}>{shortPath(path)}</code>)}
                      </div>
                    </div>
                    <div className="classification-group">
                      <div className="classification-title"><span className="classification-marker marker-possible" /><strong>Possible impact</strong><span>{bobReview.possible_impact.length}</span></div>
                      {bobReview.possible_impact.length > 0 ? (
                        <div className="file-chips">
                          {bobReview.possible_impact.map((path) => <code key={path} title={path}>{shortPath(path)}</code>)}
                        </div>
                      ) : <span className="no-files">No possible impact</span>}
                    </div>
                  </>
                )}
                <div className="classification-group last-group">
                  <div className="classification-title"><span className="classification-marker marker-unaffected" /><strong>Not affected</strong><span>{bobReview?.not_affected.length ?? report.not_affected.length}</span></div>
                  <div className="file-chips unaffected-files">
                    {(bobReview?.not_affected ?? report.not_affected).slice(0, 8).map((path) => <code key={path} title={path}>{shortPath(path)}</code>)}
                    {(bobReview?.not_affected ?? report.not_affected).length > 8 && <span className="more-files">+{(bobReview?.not_affected ?? report.not_affected).length - 8} more</span>}
                  </div>
                </div>
              </div>
            </section>
          </>
        )}

        {error && <div className="error-banner" role="alert"><span>!</span>{error}<button onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}

        <footer className="page-footer">
          <div className="footer-brand"><span className="brand-mark small"><span /><span /><span /></span><strong>CodeTwin</strong><span>·</span><span>IBM Bob Hackathon</span></div>
          <p>AST predictions are deterministic. Bob’s semantic review is an agent judgment. Merge status requires executed validation.</p>
          <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">API docs <Icon name="external" /></a>
        </footer>
      </main>
    </div>
  );
}

export default App;
