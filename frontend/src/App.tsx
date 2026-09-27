import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, apiConfigured } from './api'
import ImpactGraph, { GraphEdgeLegend, ImpactLegend } from './ImpactGraph'
import type {
  Analysis,
  AnalyzeImpactRequest,
  AnalyzeRepositoryRequest,
  GraphSnapshot,
  ImpactAnalysisResult,
  RepositoryAnalysisResult,
  TestResultFile,
} from './types'

type BusyAction = 'health' | 'repository' | 'impact' | 'session' | 'refresh' | 'tests' | 'fix' | null

function toErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Unexpected request failure.'
}

function parseWorkspaceInput(filesText: string, changedText: string): AnalyzeRepositoryRequest {
  let files: unknown
  try {
    files = JSON.parse(filesText)
  } catch {
    throw new Error('Repository files must be valid JSON: { "path.py": "source" }.')
  }
  if (!files || typeof files !== 'object' || Array.isArray(files)) {
    throw new Error('Repository files payload must be a JSON object.')
  }
  const entries = Object.entries(files)
  if (!entries.length) {
    throw new Error('Repository files payload cannot be empty.')
  }
  const normalized: Record<string, string> = {}
  for (const [key, value] of entries) {
    if (typeof key !== 'string' || !key.trim()) {
      throw new Error('Every repository file key must be a non-empty path string.')
    }
    if (typeof value !== 'string') {
      throw new Error(`Repository file ${key} must contain source code as a string.`)
    }
    normalized[key] = value
  }
  const changed_files = changedText
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)
  return { files: normalized, changed_files }
}

export default function App() {
  const [health, setHealth] = useState<'unknown' | 'ok' | 'error'>('unknown')
  const [busy, setBusy] = useState<BusyAction>(null)
  const [error, setError] = useState<string | null>(null)

  const [repositoryFilesText, setRepositoryFilesText] = useState(`{
  "app/main.py": "def run():\\n    return 1\\n"
}`)
  const [changedFilesText, setChangedFilesText] = useState('app/main.py')

  const [componentKind, setComponentKind] = useState<AnalyzeImpactRequest['component_kind']>('function')
  const [componentId, setComponentId] = useState('app/main.py::run')
  const [description, setDescription] = useState('Change runtime behavior')

  const [repositoryResult, setRepositoryResult] = useState<RepositoryAnalysisResult | null>(null)
  const [impactResult, setImpactResult] = useState<ImpactAnalysisResult | null>(null)
  const [session, setSession] = useState<Analysis | null>(null)
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let active = true
    async function checkHealth() {
      setBusy('health')
      try {
        const result = await api.checkHealth()
        if (active) setHealth(result.status === 'ok' ? 'ok' : 'error')
      } catch {
        if (active) setHealth('error')
      } finally {
        if (active) setBusy(null)
      }
    }
    if (apiConfigured) {
      void checkHealth()
    }
    return () => {
      active = false
    }
  }, [])

  const graphSnapshot: GraphSnapshot | null = useMemo(() => {
    if (!repositoryResult) return null
    return {
      analysis_id: session?.analysis_id,
      changed_files: repositoryResult.changed_files,
      predicted_impact: { files: repositoryResult.predicted_impact.files },
      dependency_edges: repositoryResult.dependency_edges,
      function_edges: repositoryResult.function_edges,
      bob_review: session?.bob_review,
    }
  }, [repositoryResult, session?.analysis_id, session?.bob_review])

  async function runRepositoryAnalysis() {
    setBusy('repository')
    setError(null)
    try {
      const payload = parseWorkspaceInput(repositoryFilesText, changedFilesText)
      const result = await api.analyzeRepository(payload)
      setRepositoryResult(result)
      setSelectedFile(result.predicted_impact.files[0] ?? null)
    } catch (requestError) {
      setError(toErrorMessage(requestError))
    } finally {
      setBusy(null)
    }
  }

  async function runImpactAnalysis() {
    setBusy('impact')
    setError(null)
    try {
      const payload = parseWorkspaceInput(repositoryFilesText, changedFilesText)
      const result = await api.analyzeImpact({
        ...payload,
        component_kind: componentKind,
        component_id: componentId.trim(),
        description: description.trim(),
      })
      setImpactResult(result)
    } catch (requestError) {
      setError(toErrorMessage(requestError))
    } finally {
      setBusy(null)
    }
  }

  async function createSession() {
    setBusy('session')
    setError(null)
    try {
      const payload = parseWorkspaceInput(repositoryFilesText, changedFilesText)
      const result = await api.createAnalysisSession(payload)
      setSession(result)
    } catch (requestError) {
      setError(toErrorMessage(requestError))
    } finally {
      setBusy(null)
    }
  }

  async function refreshSession() {
    if (!session) return
    setBusy('refresh')
    setError(null)
    try {
      setSession(await api.getAnalysis(session.analysis_id))
    } catch (requestError) {
      setError(toErrorMessage(requestError))
    } finally {
      setBusy(null)
    }
  }

  async function runTests() {
    if (!session) return
    setBusy('tests')
    setError(null)
    try {
      setSession(await api.runTargetedTests(session.analysis_id))
    } catch (requestError) {
      setError(toErrorMessage(requestError))
    } finally {
      setBusy(null)
    }
  }

  async function applyFixAndValidate() {
    if (!session) return
    setBusy('fix')
    setError(null)
    try {
      setSession(await api.applyPaymentFix(session.analysis_id))
    } catch (requestError) {
      setError(toErrorMessage(requestError))
    } finally {
      setBusy(null)
    }
  }

  async function copyBobPrompt() {
    if (!session) return
    const prompt = `Review CodeTwin analysis ${session.analysis_id}. Classify all analyzed files through CodeTwin tools and run targeted tests.`
    try {
      await navigator.clipboard.writeText(prompt)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      setError('Clipboard access failed while copying the IBM Bob prompt.')
    }
  }

  const selectedFunctions = repositoryResult?.predicted_impact.functions.filter((item) => item.file === selectedFile) ?? []
  const targetedTests = session?.predicted_impact.tests ?? []

  return (
    <div className="dashboard-root">
      <header className="header">
        <div>
          <p className="eyebrow">CodeTwin Analysis Dashboard</p>
          <h1>Deterministic Impact and Validation Console</h1>
        </div>
        <div className="header-meta">
          <Badge tone={apiConfigured ? 'ok' : 'warn'} text={apiConfigured ? 'API configured' : 'API origin required'} />
          <Badge tone={health === 'ok' ? 'ok' : health === 'error' ? 'error' : 'neutral'} text={`Health: ${health}`} />
        </div>
      </header>

      {error && <StateNotice mode="error" text={error} />}

      <Section title="1. Repository">
        <div className="grid two">
          <label className="field">
            <span>Repository snapshot JSON</span>
            <textarea value={repositoryFilesText} onChange={(event) => setRepositoryFilesText(event.target.value)} rows={9} />
          </label>
          <label className="field">
            <span>Changed files (comma or newline separated)</span>
            <textarea value={changedFilesText} onChange={(event) => setChangedFilesText(event.target.value)} rows={9} />
          </label>
        </div>
      </Section>

      <Section title="2. Proposed Change">
        <div className="grid three">
          <label className="field">
            <span>Component kind</span>
            <select value={componentKind} onChange={(event) => setComponentKind(event.target.value as AnalyzeImpactRequest['component_kind'])}>
              <option value="file">file</option>
              <option value="module">module</option>
              <option value="function">function</option>
              <option value="class">class</option>
              <option value="api_endpoint">api_endpoint</option>
              <option value="test">test</option>
            </select>
          </label>
          <label className="field">
            <span>Component ID</span>
            <input value={componentId} onChange={(event) => setComponentId(event.target.value)} />
          </label>
          <label className="field">
            <span>Description</span>
            <input value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
        </div>
      </Section>

      <Section title="3. Analyze Impact">
        <div className="actions">
          <button onClick={runRepositoryAnalysis} disabled={busy !== null}>{busy === 'repository' ? 'Analyzing repository…' : 'Analyze Repository'}</button>
          <button onClick={runImpactAnalysis} disabled={busy !== null}>{busy === 'impact' ? 'Analyzing impact…' : 'Analyze Impact'}</button>
          <button onClick={createSession} disabled={busy !== null}>{busy === 'session' ? 'Creating validation session…' : 'Create IBM Bob Validation Session'}</button>
        </div>
      </Section>

      <Section title="4. Impact Summary">
        {!repositoryResult && !impactResult ? (
          <StateNotice mode="empty" text="Run repository or impact analysis to populate summary metrics." />
        ) : (
          <div className="stats">
            <Stat label="Impacted Files" value={repositoryResult?.predicted_impact.files.length ?? impactResult?.affected_files.length ?? 0} />
            <Stat label="Impacted Functions" value={repositoryResult?.predicted_impact.functions.length ?? impactResult?.affected_functions.length ?? 0} />
            <Stat label="Impacted APIs" value={repositoryResult?.predicted_impact.api_routes.length ?? impactResult?.affected_apis.length ?? 0} />
            <Stat label="Targeted Tests" value={repositoryResult?.predicted_impact.tests.length ?? impactResult?.affected_tests.length ?? 0} />
          </div>
        )}
      </Section>

      <Section title="5. Dependency Graph">
        {!graphSnapshot ? (
          <StateNotice mode="empty" text="Analyze the repository to render dependency and call relationships." />
        ) : (
          <>
            <ImpactGraph analysis={graphSnapshot} selectedFile={selectedFile} onSelectFile={setSelectedFile} />
            <div className="legend-row">
              <ImpactLegend bobReviewed={session?.bob_review?.status === 'complete'} />
              <GraphEdgeLegend edges={[...graphSnapshot.dependency_edges, ...graphSnapshot.function_edges]} />
            </div>
          </>
        )}
      </Section>

      <Section title="6. Predicted Impact">
        {!repositoryResult && !impactResult ? (
          <StateNotice mode="empty" text="No predicted impact yet." />
        ) : (
          <div className="grid two">
            <article className="subpanel">
              <h3>Repository analysis files</h3>
              {repositoryResult?.predicted_impact.files.length ? (
                <ul className="list">
                  {repositoryResult.predicted_impact.files.map((file) => <li key={file}>{file}</li>)}
                </ul>
              ) : <StateNotice mode="empty" text="No impacted files from repository analysis." />}
            </article>
            <article className="subpanel">
              <h3>Impact engine functions</h3>
              {impactResult?.affected_functions.length ? (
                <ul className="list">
                  {impactResult.affected_functions.map((item) => <li key={item.component_id}>{item.component_id}</li>)}
                </ul>
              ) : <StateNotice mode="empty" text="No impacted functions from impact engine." />}
            </article>
          </div>
        )}
        {selectedFile && selectedFunctions.length > 0 && (
          <div className="selection-hint">Selected {selectedFile} exposes: {selectedFunctions.map((item) => item.qualname).join(', ')}</div>
        )}
      </Section>

      <Section title="7. IBM Bob Validation">
        {!session ? (
          <StateNotice mode="empty" text="Create a validation session to track IBM Bob review status." />
        ) : (
          <div className="subpanel">
            <p><strong>Analysis ID:</strong> {session.analysis_id}</p>
            <div className="actions">
              <button onClick={refreshSession} disabled={busy !== null}>{busy === 'refresh' ? 'Refreshing…' : 'Refresh Session'}</button>
              <button onClick={copyBobPrompt}> {copied ? 'Prompt copied' : 'Copy Bob Prompt'} </button>
            </div>
            {session.bob_review ? (
              <div className="grid three compact-grid">
                <Stat label="Confirmed" value={session.bob_review.bob_confirmed_impact.length} />
                <Stat label="Possible" value={session.bob_review.possible_impact.length} />
                <Stat label="Not Affected" value={session.bob_review.not_affected.length} />
              </div>
            ) : <StateNotice mode="loading" text="Waiting for IBM Bob review submission." />}
          </div>
        )}
      </Section>

      <Section title="8. Regression Status">
        {!session ? (
          <StateNotice mode="empty" text="Regression status becomes available after creating a validation session." />
        ) : (
          <div className="subpanel">
            <p><strong>Status:</strong> {session.status}</p>
            <p><strong>Safe to merge:</strong> {session.safe_to_merge ? 'yes' : 'no'}</p>
          </div>
        )}
      </Section>

      <Section title="9. Tests">
        {!session ? (
          <StateNotice mode="empty" text="Create a session to run targeted tests." />
        ) : (
          <div className="subpanel">
            <div className="actions">
              <button onClick={runTests} disabled={busy !== null}>{busy === 'tests' ? 'Running tests…' : 'Run Targeted Tests'}</button>
            </div>
            <p>Selected tests: {targetedTests.length ? targetedTests.join(', ') : 'none selected'}</p>
            <p>Runner status: {session.test_results.status}</p>
            {session.test_results.results.length ? (
              <div className="test-list">
                {session.test_results.results.map((result) => <TestResult key={result.file} result={result} />)}
              </div>
            ) : <StateNotice mode="empty" text="No executed test results yet." />}
          </div>
        )}
      </Section>

      <Section title="10. Fix & Validate">
        {!session ? (
          <StateNotice mode="empty" text="Fix flow requires an existing analysis session." />
        ) : (
          <div className="subpanel">
            <p>Use this action only when your backend supports demo or scenario fix generation for the current analysis.</p>
            <button onClick={applyFixAndValidate} disabled={busy !== null}>{busy === 'fix' ? 'Applying fix…' : 'Apply Fix and Re-Validate'}</button>
          </div>
        )}
      </Section>

      <Section title="11. Final Status">
        {!session ? (
          <StateNotice mode="empty" text="Final merge status is shown after validation session progresses." />
        ) : (
          <div className="subpanel">
            <ul className="checklist">
              <GateItem done={session.bob_review?.status === 'complete'} label="IBM Bob review completed" />
              <GateItem done={session.test_results.passed} label="Targeted tests passed" />
              <GateItem done={session.parse_errors.length === 0} label="No parse errors" />
              <GateItem done={session.safe_to_merge} label="Safe to merge" />
            </ul>
          </div>
        )}
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  )
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

function Badge({ text, tone }: { text: string; tone: 'ok' | 'warn' | 'error' | 'neutral' }) {
  return <span className={`badge badge-${tone}`}>{text}</span>
}

function StateNotice({ mode, text }: { mode: 'loading' | 'empty' | 'error'; text: string }) {
  return <div className={`notice notice-${mode}`}>{text}</div>
}

function GateItem({ done, label }: { done: boolean; label: string }) {
  return <li className={done ? 'done' : 'pending'}>{done ? '✓' : '•'} {label}</li>
}

function TestResult({ result }: { result: TestResultFile }) {
  return (
    <details className={`test-item ${result.status}`}>
      <summary>{result.file} · {result.runner} · {result.status}</summary>
      <pre>{result.output || 'No output from test runner.'}</pre>
    </details>
  )
}
