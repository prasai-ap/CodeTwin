import { useCallback, useEffect, useMemo, useState } from 'react'
import { api, apiConfigured } from './api'
import { GraphEdgeLegend, ImpactLegend } from './ImpactGraph'
import ImpactGraph from './ImpactGraph'
import type { Analysis, AnalysisStatus, TestResultFile } from './types'

type Action = 'analyze' | 'fix' | 'tests' | 'refresh' | null

const statusCopy: Record<AnalysisStatus, { title: string; detail: string; icon: string }> = {
  awaiting_bob_review: {
    title: 'Waiting on IBM Bob',
    detail: 'The deterministic impact map is ready. Bob must inspect the captured repository and classify its files.',
    icon: '◷',
  },
  awaiting_tests: {
    title: 'Impact reviewed · tests not run',
    detail: 'Bob has completed the semantic review. Run the selected tests to validate this snapshot.',
    icon: '◉',
  },
  safe_to_merge: {
    title: 'Safe to Merge',
    detail: 'Bob review is complete and every selected test passed against this captured snapshot.',
    icon: '✓',
  },
  regression_detected: {
    title: 'Regression detected',
    detail: 'A targeted test failed. The merge gate stays closed until the change is fixed and checked again.',
    icon: '!',
  },
  possible_impact_unresolved: {
    title: 'Possible impact needs a decision',
    detail: 'Tests passed, but Bob marked at least one file as possible impact. Resolve it before merging.',
    icon: '?',
  },
  analysis_errors: {
    title: 'Analysis has errors',
    detail: 'One or more Python files could not be parsed. Resolve the analysis error before merging.',
    icon: '!',
  },
  test_execution_error: {
    title: 'Test execution needs attention',
    detail: 'The targeted checks could not complete successfully. Review the execution output below.',
    icon: '!',
  },
  no_targeted_tests: {
    title: 'No targeted tests found',
    detail: 'The analyzer did not select any tests for this change, so the merge gate stays closed.',
    icon: '—',
  },
}

function shortPath(path: string) {
  return path.split('/').slice(-2).join('/')
}

function humanTime(date: Date | null) {
  if (!date) return 'Not analyzed yet'
  return `Updated ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
}

function asErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'CodeTwin could not complete that request.'
}

export default function App() {
  const [analysis, setAnalysis] = useState<Analysis | null>(null)
  const [action, setAction] = useState<Action>(null)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const withAction = useCallback(async (name: Exclude<Action, null>, operation: () => Promise<Analysis>) => {
    setAction(name)
    setError(null)
    try {
      const next = await operation()
      setAnalysis(next)
      setLastUpdated(new Date())
      return next
    } catch (requestError) {
      setError(asErrorMessage(requestError))
      return null
    } finally {
      setAction(null)
    }
  }, [])

  const startDemo = useCallback(() => withAction('analyze', async () => {
    const next = await api.startPaymentDemo()
    setSelectedFile(next.changed_files[0] ?? null)
    return next
  }), [withAction])

  const runTests = useCallback(() => {
    if (!analysis) return Promise.resolve(null)
    return withAction('tests', () => api.runTargetedTests(analysis.analysis_id))
  }, [analysis, withAction])

  useEffect(() => {
    if (!analysis || action || !['awaiting_bob_review', 'awaiting_tests'].includes(analysis.status)) return
    let active = true
    const timer = window.setInterval(async () => {
      try {
        const next = await api.getAnalysis(analysis.analysis_id)
        if (active) {
          setAnalysis(next)
          setLastUpdated(new Date())
        }
      } catch {
        // Keep the last known review visible while the API is temporarily unavailable.
      }
    }, 3500)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [analysis?.analysis_id, analysis?.status, action])

  const selectedFunctions = useMemo(
    () => analysis?.predicted_impact.functions.filter((item) => item.file === selectedFile) ?? [],
    [analysis, selectedFile],
  )

  async function copyBobPrompt() {
    if (!analysis) return
    const prompt = `Review CodeTwin analysis ${analysis.analysis_id}. Use the CodeTwin MCP tools to inspect its captured source, independently classify all analyzed files, submit your review, and run the targeted tests. Do not report Safe to Merge unless CodeTwin returns that status.`
    try {
      await navigator.clipboard.writeText(prompt)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setError('Could not copy the Bob review prompt. You can copy the analysis ID from the panel.')
    }
  }

  async function refreshAnalysis() {
    if (!analysis) return
    await withAction('refresh', () => api.getAnalysis(analysis.analysis_id))
  }

  async function applyFix() {
    if (!analysis) return
    await withAction('fix', async () => {
      const next = await api.applyPaymentFix(analysis.analysis_id)
      setSelectedFile(next.changed_files[0] ?? null)
      return next
    })
  }

  const busy = action !== null
  const bobReview = analysis?.bob_review
  const bobReviewed = bobReview?.status === 'complete'
  const targetedTests = analysis?.predicted_impact.tests ?? []

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#top" aria-label="CodeTwin home">
          <span className="brand-mark"><span /><span /><span /></span>
          <span className="brand-word">code<span>twin</span></span>
        </a>
        <div className="topbar-meta">
          <span className="topbar-project"><i className="status-dot" /> PAYMENT FLOW DEMO</span>
          <span className={`api-indicator${apiConfigured ? ' is-ready' : ' is-missing'}`}>
            <i />{apiConfigured ? 'API configured' : 'API origin required'}
          </span>
          <span className="avatar">CT</span>
        </div>
      </header>

      <main id="top" className="main-content">
        <section className="page-heading">
          <div>
            <div className="eyebrow"><span className="eyebrow-line" /> CHANGE IMPACT WORKSPACE</div>
            <h1>Know what your change <span>touches.</span></h1>
            <p>Trace downstream impact, get Bob’s independent review, then validate with targeted tests.</p>
          </div>
          {analysis && (
            <button className="button button-quiet refresh-button" onClick={refreshAnalysis} disabled={busy}>
              <span className={action === 'refresh' ? 'spin' : ''}>↻</span> Refresh review
            </button>
          )}
        </section>

        <section className="change-strip" aria-label="Repository and proposed change">
          <div className="repository-card">
            <div className="card-kicker">REPOSITORY</div>
            <div className="repo-title-row">
              <span className="repo-icon">⌘</span>
              <div>
                <h2>ecommerce</h2>
                <p>examples/ecommerce <span className="repo-separator">·</span> FastAPI service</p>
              </div>
              <span className="demo-tag">SYNTHETIC</span>
            </div>
            <div className="repo-footer"><span className="branch-icon">⑂</span> main <span className="repo-separator">/</span> working tree <span className="repo-file-count">Python AST</span></div>
          </div>

          <div className="change-card">
            <div className="change-card-copy">
              <div className="card-kicker">PROPOSED CHANGE <span className="change-file">{shortPath(analysis?.changed_files[0] ?? 'app/payments/service.py')}</span></div>
              <div className="change-flow">
                <span className="flow-state flow-before">pending</span>
                <span className="flow-arrow">→</span>
                <span className="flow-state flow-new">authorized</span>
                <span className="flow-arrow">→</span>
                <span className="flow-state flow-after">completed</span>
              </div>
              <p className="change-description">Payment capture adds an authorization step before completion.</p>
            </div>
            <button className="button button-primary analyze-button" onClick={startDemo} disabled={busy}>
              {action === 'analyze' ? <><span className="button-spinner" /> Analyzing…</> : <><span className="button-spark">✳</span> {analysis ? 'Analyze again' : 'Analyze Impact'} <span className="button-arrow">↗</span></>}
            </button>
          </div>
        </section>

        {error && <div className="error-banner" role="alert"><span>!</span><p>{error}</p><button onClick={() => setError(null)} aria-label="Dismiss error">×</button></div>}

        {!analysis ? (
          <section className="welcome-panel">
            <div className="welcome-graphic" aria-hidden="true">
              <span className="welcome-orbit orbit-one" /><span className="welcome-orbit orbit-two" />
              <span className="welcome-node welcome-node-main">pay</span>
              <span className="welcome-node welcome-node-a">notify</span>
              <span className="welcome-node welcome-node-b">orders</span>
              <span className="welcome-node welcome-node-c">tests</span>
              <span className="welcome-link link-one" /><span className="welcome-link link-two" /><span className="welcome-link link-three" />
            </div>
            <div className="welcome-copy">
              <div className="eyebrow">A REAL REGRESSION. A REAL TEST.</div>
              <h2>Start with the payment change.</h2>
              <p>The demo adds <code>authorized</code> to the payment workflow. A notification consumer still assumes <code>pending → completed</code>, and the checkout test proves where the regression lands.</p>
              <div className="welcome-steps">
                <span><b>01</b> Analyze the graph</span><span><b>02</b> Ask Bob to review</span><span><b>03</b> Run the test</span>
              </div>
            </div>
            <div className="welcome-count"><span>01</span><small>DEMO SCENARIO</small></div>
          </section>
        ) : (
          <>
            <section className={`status-banner status-${analysis.status}`} aria-live="polite">
              <span className="status-icon">{statusCopy[analysis.status].icon}</span>
              <div className="status-copy"><h2>{statusCopy[analysis.status].title}</h2><p>{statusCopy[analysis.status].detail}</p></div>
              <div className="status-meta"><span className="status-pill"><i />{analysis.status.replaceAll('_', ' ')}</span><span>{humanTime(lastUpdated)}</span></div>
            </section>

            <section className="metric-row" aria-label="Impact summary">
              <Metric label="FILES IN IMPACT GRAPH" value={analysis.predicted_impact.files.length} detail={`${analysis.changed_files.length} changed`} accent="cyan" />
              <Metric label="FUNCTIONS & METHODS" value={analysis.predicted_impact.functions.length} detail="AST call relationships" accent="violet" />
              <Metric label="API ROUTES" value={analysis.predicted_impact.api_routes.length} detail="reachable endpoints" accent="blue" />
              <Metric label="TARGETED TESTS" value={targetedTests.length} detail={analysis.test_results.status === 'not_run' ? 'waiting to execute' : analysis.test_results.status} accent={analysis.test_results.passed ? 'green' : 'amber'} />
            </section>

            <section className="workspace-grid">
              <article className="panel graph-panel">
                <div className="panel-heading">
                  <div><div className="panel-kicker">DETERMINISTIC ANALYSIS</div><h2>Impact graph <span className="heading-count">{analysis.predicted_impact.files.length} files</span></h2></div>
                  <span className="graph-engine"><i /> PYTHON AST</span>
                </div>
                <p className="panel-subtitle">Impact flows from the changed payment service into its downstream callers and tests.</p>
                <ImpactGraph analysis={analysis} selectedFile={selectedFile} onSelectFile={setSelectedFile} />
                <div className="graph-footer"><ImpactLegend bobReviewed={bobReviewed} /><GraphEdgeLegend edges={[...analysis.dependency_edges, ...analysis.function_edges]} /></div>
                {selectedFile && (
                  <div className="selected-node-detail">
                    <span className="detail-file-icon">ƒ</span>
                    <div className="selected-file-copy"><code>{selectedFile}</code><small>{selectedFunctions.length ? selectedFunctions.map((fn) => `${fn.qualname} · L${fn.line}`).join('  /  ') : 'File relationship in the deterministic impact graph'}</small></div>
                    <button className="detail-clear" onClick={() => setSelectedFile(null)} aria-label="Clear selected file">×</button>
                  </div>
                )}
              </article>

              <div className="review-column">
                <article className={`panel bob-panel${bobReviewed ? ' bob-complete' : ''}`}>
                  <div className="panel-heading">
                    <div><div className="panel-kicker">SEMANTIC REVIEW</div><h2>IBM Bob <span className={`review-state${bobReviewed ? ' is-complete' : ''}`}><i />{bobReviewed ? 'Reviewed' : 'Waiting'}</span></h2></div>
                    <span className="bob-mark">B</span>
                  </div>
                  {!bobReviewed ? (
                    <>
                      <p className="bob-description">Bob inspects the captured source and validates the predicted downstream impact. Its judgment is recorded separately from the AST graph.</p>
                      <div className="analysis-id-row"><span>ANALYSIS ID</span><code>{analysis.analysis_id}</code></div>
                      <button className="button button-secondary copy-prompt" onClick={copyBobPrompt}>{copied ? '✓ Prompt copied' : 'Copy Bob review prompt'} <span>↗</span></button>
                      <div className="bob-hint"><span className="hint-orb">i</span><p>Open this workspace in Bob and ask it to review the analysis using the CodeTwin MCP tools.</p></div>
                    </>
                  ) : (
                    <>
                      <p className="bob-description">Bob inspected the snapshot and submitted a complete semantic review.</p>
                      <div className="review-counts">
                        <ReviewCount label="CONFIRMED" value={bobReview?.bob_confirmed_impact.length ?? 0} kind="confirmed" />
                        <ReviewCount label="POSSIBLE" value={bobReview?.possible_impact.length ?? 0} kind="possible" />
                        <ReviewCount label="NOT AFFECTED" value={bobReview?.not_affected.length ?? 0} kind="unaffected" />
                      </div>
                      <blockquote className="bob-rationale">“{bobReview?.rationale}”</blockquote>
                    </>
                  )}
                  {bobReviewed && (
                    <button className="button button-secondary run-tests-button" onClick={runTests} disabled={busy}>
                      {action === 'tests' ? <><span className="button-spinner" /> Running tests…</> : <>{analysis.test_results.status === 'not_run' ? 'Run targeted tests' : 'Run tests again'} <span>→</span></>}
                    </button>
                  )}
                </article>

                <article className="panel gate-panel">
                  <div className="gate-heading"><span className={`gate-shield${analysis.safe_to_merge ? ' gate-is-safe' : ''}`}>{analysis.safe_to_merge ? '✓' : '⌑'}</span><div><div className="panel-kicker">MERGE GATE</div><h3>{analysis.safe_to_merge ? 'Safe to Merge' : 'Not ready to merge'}</h3></div></div>
                  <div className="gate-checks">
                    <GateCheck done={bobReviewed} label="IBM Bob semantic review" />
                    <GateCheck done={analysis.parse_errors.length === 0} label="Python source parsed" />
                    <GateCheck done={analysis.test_results.passed && targetedTests.length > 0} label="Targeted tests passed" />
                    <GateCheck done={Boolean(bobReview && bobReview.possible_impact.length === 0)} label="No unresolved possible impact" />
                  </div>
                  {analysis.status === 'regression_detected' && (
                    <button className="button button-fix" onClick={applyFix} disabled={busy}>
                      {action === 'fix' ? <><span className="button-spinner" /> Applying fix…</> : <>Fix &amp; Validate <span>→</span></>}
                    </button>
                  )}
                </article>
              </div>
            </section>

            <section className="detail-grid">
              <article className="panel detail-panel">
                <div className="panel-heading"><div><div className="panel-kicker">FILE LEVEL</div><h2>Affected files <span className="heading-count">{analysis.predicted_impact.files.length}</span></h2></div><span className="panel-side-note">Select a graph node to inspect</span></div>
                <div className="file-list">
                  {analysis.predicted_impact.files.map((file) => {
                    const assessment = analysis.bob_review?.file_assessments[file]
                    const changed = analysis.changed_files.includes(file)
                    return (
                      <button className={`file-row${selectedFile === file ? ' file-row-selected' : ''}`} key={file} onClick={() => setSelectedFile(file)}>
                        <span className={`file-symbol${changed ? ' file-symbol-changed' : ''}`}>{changed ? 'Δ' : 'ƒ'}</span>
                        <span className="file-path"><code>{file}</code><small>{assessment?.prediction === 'predicted_impact' ? 'Static dependency or call relationship' : 'Changed source file'}</small></span>
                        <span className={`file-badge ${assessment?.bob_assessment ?? (changed ? 'changed' : 'predicted')}`}>{assessment?.bob_assessment === 'bob_confirmed_impact' ? 'Bob confirmed' : assessment?.bob_assessment === 'possible_impact' ? 'Possible' : assessment?.bob_assessment === 'not_affected' ? 'Not affected' : changed ? 'Changed' : 'Predicted'}</span>
                      </button>
                    )
                  })}
                </div>
                <div className="unpredicted-block">
                  <div className="unpredicted-heading"><span>Outside predicted graph</span><span>{analysis.bob_review ? 'BOB REVIEW' : 'AWAITING BOB'}</span></div>
                  {analysis.bob_review ? (
                    <div className="classification-groups">
                      {(['bob_confirmed_impact', 'possible_impact', 'not_affected'] as const).map((kind) => {
                        const files = Object.entries(analysis.bob_review!.file_assessments)
                          .filter(([, assessment]) => assessment.prediction === 'not_predicted' && assessment.bob_assessment === kind)
                          .map(([file]) => file)
                        if (!files.length) return null
                        const label = kind === 'bob_confirmed_impact' ? 'BOB CONFIRMED' : kind === 'possible_impact' ? 'POSSIBLE IMPACT' : 'NOT AFFECTED'
                        return <div className="classification-row" key={kind}><span className={`classification-label classification-${kind}`}>{label}</span><div className="outside-file-list">{files.slice(0, 5).map((file) => <code key={file}>{file}</code>)}{files.length > 5 && <small>+{files.length - 5} more</small>}</div></div>
                      })}
                      {!analysis.bob_review.file_assessments || Object.values(analysis.bob_review.file_assessments).every((assessment) => assessment.prediction === 'predicted_impact') ? <p className="outside-empty">Bob found no files outside the predicted graph.</p> : null}
                    </div>
                  ) : (
                    <div className="outside-file-list">{analysis.not_affected.slice(0, 4).map((file) => <code key={file}>{file}</code>)}{analysis.not_affected.length > 4 && <small>+{analysis.not_affected.length - 4} more</small>}{analysis.not_affected.length === 0 && <small>No unpredicted source files.</small>}</div>
                  )}
                </div>
              </article>

              <article className="panel detail-panel api-panel">
                <div className="panel-heading"><div><div className="panel-kicker">DOWNSTREAM CONTRACTS</div><h2>Affected APIs <span className="heading-count">{analysis.predicted_impact.api_routes.length}</span></h2></div><span className="api-code-mark">/</span></div>
                {analysis.predicted_impact.api_routes.length ? (
                  <div className="endpoint-list">
                    {analysis.predicted_impact.api_routes.map((route) => (
                      <div className="endpoint-row" key={`${route.method}-${route.path}-${route.handler}`}>
                        <span className={`method-tag method-${route.method.toLowerCase()}`}>{route.method}</span>
                        <div className="endpoint-info"><code>{route.path}</code><small>{route.file} <span>·</span> {route.handler}()</small></div>
                        <span className="endpoint-impact">impacted</span>
                      </div>
                    ))}
                  </div>
                ) : <EmptyDetail text="No API route was found in the predicted impact graph." />}
                <div className="class-impact-block">
                  <div className="class-impact-heading"><span className="component-label">CLASSES IN PREDICTED FILES</span><span className="heading-count">{analysis.predicted_impact.classes.length}</span></div>
                  {analysis.predicted_impact.classes.length ? (
                    <div className="class-impact-list">
                      {analysis.predicted_impact.classes.map((item) => (
                        <div className="class-impact-item" key={item.id}>
                          <code>{item.qualname}</code>
                          <small>{item.file} · L{item.line}</small>
                        </div>
                      ))}
                    </div>
                  ) : <p className="class-impact-empty">No class definitions were found in the predicted files.</p>}
                </div>
                <div className="component-tags"><span className="component-label">COMPONENTS</span>{analysis.predicted_impact.components.slice(0, 7).map((component) => <span className="component-tag" key={component}>{component}</span>)}</div>
              </article>
            </section>

            <section className="panel tests-panel">
              <div className="panel-heading tests-heading">
                <div><div className="panel-kicker">EXECUTED VALIDATION</div><h2>Targeted tests <span className="heading-count">{targetedTests.length} selected</span></h2></div>
                <span className={`tests-summary tests-${analysis.test_results.status}`}><i />{analysis.test_results.status === 'not_run' ? 'Not run yet' : analysis.test_results.passed ? 'All checks passed' : analysis.test_results.status.replaceAll('_', ' ')}</span>
              </div>
              {analysis.test_results.status === 'not_run' ? (
                <div className="tests-pending"><span className="pending-clock">◷</span><div><strong>{targetedTests.length ? 'Waiting for Bob to run the selected tests' : 'No tests selected for this change'}</strong><p>{targetedTests.length ? targetedTests.join(' · ') : 'A passing test result is required before merge safety can be assessed.'}</p></div>{bobReviewed && <button className="button button-small button-secondary" onClick={runTests} disabled={busy}>{action === 'tests' ? 'Running…' : 'Run tests'}</button>}</div>
              ) : (
                <div className="test-results-list">
                  {analysis.test_results.results.map((result) => <TestResult key={result.file} result={result} />)}
                </div>
              )}
              <div className="test-footnote"><span>ⓘ</span> Tests run against the captured analysis snapshot in an isolated temporary directory.</div>
            </section>

            {analysis.parse_errors.length > 0 && (
              <section className="panel parse-error-panel"><div className="panel-kicker">ANALYSIS ERRORS</div>{analysis.parse_errors.map((item) => <p key={item.file}><code>{item.file}</code> — {item.message}</p>)}</section>
            )}
            <footer className="session-footer"><span><i className="status-dot" /> SESSION {analysis.analysis_id.slice(0, 12)}</span><span>{analysis.demo_scenario?.description ?? 'Captured Python repository snapshot'}</span><button onClick={refreshAnalysis} disabled={busy}>{action === 'refresh' ? 'Refreshing…' : 'Sync status ↻'}</button></footer>
          </>
        )}

        <footer className="app-footer"><span>CodeTwin <b>·</b> Impact analysis for the changes that matter.</span><span>Deterministic graph <i /> IBM Bob review <i /> Executed tests</span></footer>
      </main>
    </div>
  )
}

function Metric({ label, value, detail, accent }: { label: string; value: number; detail: string; accent: string }) {
  return <article className="metric-card"><div className={`metric-icon metric-${accent}`}><span /></div><div className="metric-content"><div className="metric-label">{label}</div><div className="metric-value-row"><strong>{value}</strong><span>{detail}</span></div></div><span className={`metric-line metric-line-${accent}`} /></article>
}

function ReviewCount({ label, value, kind }: { label: string; value: number; kind: string }) {
  return <div className={`review-count review-count-${kind}`}><strong>{value}</strong><span>{label}</span></div>
}

function GateCheck({ done, label }: { done: boolean; label: string }) {
  return <div className={`gate-check${done ? ' gate-check-done' : ''}`}><span>{done ? '✓' : '·'}</span>{label}</div>
}

function EmptyDetail({ text }: { text: string }) {
  return <div className="empty-detail">{text}</div>
}

function TestResult({ result }: { result: TestResultFile }) {
  const passed = result.status === 'passed'
  return (
    <details className={`test-result${passed ? ' test-passed' : ' test-failed'}`}>
      <summary><span className="test-status-icon">{passed ? '✓' : result.status === 'timeout' ? '◷' : '!'}</span><code>{result.file}</code><span className="test-runner-tag">{result.runner}</span><span className={`test-status-label ${passed ? 'label-passed' : 'label-failed'}`}>{result.status}</span><span className="disclosure-arrow">⌄</span></summary>
      <pre>{result.output || 'The test runner returned no output.'}</pre>
    </details>
  )
}
