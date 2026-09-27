import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, apiConfigured } from './api'
import type {
  AnalyzeRepositoryRequest,
  DependencyPath,
  ImpactAnalysisResult,
  ImpactedComponent,
  RepositoryAnalysisResult,
} from './types'

type BusyState = 'health' | 'analyzing' | null

type PipelineResult = {
  repository: RepositoryAnalysisResult
  impact: ImpactAnalysisResult
}

function toErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : 'Unexpected request failure.'
}

function parseRequest(filesText: string, changedFilesText: string): AnalyzeRepositoryRequest {
  let parsedFiles: unknown
  try {
    parsedFiles = JSON.parse(filesText)
  } catch {
    throw new Error('Repository JSON must be valid, for example: { "app/main.py": "def run():\\n  return 1" }.')
  }
  if (!parsedFiles || typeof parsedFiles !== 'object' || Array.isArray(parsedFiles)) {
    throw new Error('Repository JSON must be an object of file path to source string.')
  }

  const files = Object.entries(parsedFiles)
  if (!files.length) {
    throw new Error('Repository JSON cannot be empty.')
  }

  const normalizedFiles: Record<string, string> = {}
  for (const [path, source] of files) {
    if (!path.trim()) {
      throw new Error('Every file path must be non-empty.')
    }
    if (typeof source !== 'string') {
      throw new Error(`Source for ${path} must be a string.`)
    }
    normalizedFiles[path] = source
  }

  const changedFiles = changedFilesText
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean)

  return {
    files: normalizedFiles,
    changed_files: changedFiles,
  }
}

function defaultImpactComponent(repository: RepositoryAnalysisResult): { kind: 'file' | 'module' | 'function' | 'class' | 'api_endpoint' | 'test'; id: string } | null {
  const firstFunction = repository.predicted_impact.functions[0]
  if (firstFunction) {
    return { kind: 'function', id: firstFunction.id }
  }
  const firstClass = repository.predicted_impact.classes[0]
  if (firstClass) {
    return { kind: 'class', id: firstClass.id }
  }
  const firstFile = repository.changed_files[0] ?? repository.predicted_impact.files[0]
  if (!firstFile) return null
  return { kind: 'file', id: firstFile }
}

export default function App() {
  const [health, setHealth] = useState<'unknown' | 'ok' | 'error'>('unknown')
  const [busy, setBusy] = useState<BusyState>(null)
  const [error, setError] = useState<string | null>(null)

  const [filesInput, setFilesInput] = useState(`{
  "app/domain.py": "def calculate_total():\\n    return 42\\n",
  "app/service.py": "from app.domain import calculate_total\\ndef get_total():\\n    return calculate_total()\\n",
  "app/api.py": "from fastapi import APIRouter\\nfrom app.service import get_total\\nrouter = APIRouter(prefix='/totals')\\n@router.get('')\\ndef read_total():\\n    return get_total()\\n",
  "tests/test_api.py": "from app.api import read_total\\ndef test_read_total():\\n    assert read_total() == 42\\n"
}`)
  const [changedFilesInput, setChangedFilesInput] = useState('app/domain.py')
  const [impactDescription, setImpactDescription] = useState('Adjust total calculation behavior')

  const [result, setResult] = useState<PipelineResult | null>(null)

  useEffect(() => {
    if (!apiConfigured) return
    let active = true

    async function checkHealth() {
      setBusy('health')
      try {
        const response = await api.checkHealth()
        if (active) {
          setHealth(response.status === 'ok' ? 'ok' : 'error')
        }
      } catch {
        if (active) setHealth('error')
      } finally {
        if (active) setBusy(null)
      }
    }

    void checkHealth()
    return () => {
      active = false
    }
  }, [])

  const predictedImpactLabel = useMemo(() => {
    if (!result) return null
    const label = result.impact.affected_files[0]?.label
    return label || 'PREDICTED IMPACT'
  }, [result])

  async function runPipeline() {
    setBusy('analyzing')
    setError(null)

    try {
      const request = parseRequest(filesInput, changedFilesInput)
      const repository = await api.analyzeRepository(request)

      const component = defaultImpactComponent(repository)
      if (!component) {
        setResult({
          repository,
          impact: {
            status: 'success',
            proposed_change: {
              component_kind: 'file',
              component_id: '',
              description: impactDescription.trim() || 'Predicted impact from changed files',
            },
            affected_files: [],
            affected_modules: [],
            affected_functions: [],
            affected_classes: [],
            affected_apis: [],
            affected_tests: [],
            dependency_paths: [],
            risk_indicators: [],
          },
        })
        return
      }

      const impact = await api.analyzeImpact({
        files: request.files,
        component_kind: component.kind,
        component_id: component.id,
        description: impactDescription.trim() || `Impact analysis for ${component.id}`,
      })

      setResult({ repository, impact })
    } catch (requestError) {
      setError(toErrorMessage(requestError))
      setResult(null)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="dashboard-root">
      <header className="header">
        <div>
          <p className="eyebrow">CodeTwin Frontend</p>
          <h1>Repository to Predicted Impact Pipeline</h1>
        </div>
        <div className="header-meta">
          <StatusBadge tone={apiConfigured ? 'ok' : 'warn'} text={apiConfigured ? 'API configured' : 'API origin required'} />
          <StatusBadge tone={health === 'ok' ? 'ok' : health === 'error' ? 'error' : 'neutral'} text={`Health ${health}`} />
        </div>
      </header>

      {error && <Notice kind="error" text={error} />}

      <Section title="Repository analysis">
        <div className="grid two">
          <Field label="Repository files JSON">
            <textarea rows={11} value={filesInput} onChange={(event) => setFilesInput(event.target.value)} />
          </Field>
          <div className="stack">
            <Field label="Changed files">
              <textarea rows={4} value={changedFilesInput} onChange={(event) => setChangedFilesInput(event.target.value)} />
            </Field>
            <Field label="Impact analysis description">
              <textarea rows={4} value={impactDescription} onChange={(event) => setImpactDescription(event.target.value)} />
            </Field>
            <div className="actions">
              <button onClick={runPipeline} disabled={busy !== null || !apiConfigured}>
                {busy === 'analyzing' ? 'Analyzing repository then impact...' : 'Run analysis pipeline'}
              </button>
            </div>
            <p className="note">
              Flow: Repository analysis {'>'} Impact analysis {'>'} Display actual result
            </p>
          </div>
        </div>
      </Section>

      {!result && busy === 'analyzing' && <Notice kind="loading" text="Running repository analysis and impact analysis..." />}

      {!result && busy !== 'analyzing' && !error && (
        <Notice kind="empty" text="Run the analysis pipeline to display predicted impact details." />
      )}

      {result && (
        <>
          <Section title="Current result">
            <div className="result-banner">
              <span className="result-label">{predictedImpactLabel}</span>
              <span className="result-subtitle">Deterministic static analysis result, not IBM Bob semantic validation.</span>
            </div>
          </Section>

          <Section title="Predicted impact summary">
            <div className="stats">
              <Stat label="Affected files" value={result.repository.predicted_impact.files.length} />
              <Stat label="Functions" value={result.impact.affected_functions.length} />
              <Stat label="Classes" value={result.impact.affected_classes.length} />
              <Stat label="APIs" value={result.impact.affected_apis.length} />
              <Stat label="Tests" value={result.impact.affected_tests.length} />
              <Stat label="Dependency paths" value={result.impact.dependency_paths.length} />
              <Stat label="Risk indicators" value={result.impact.risk_indicators.length} />
            </div>
          </Section>

          <Section title="Affected files">
            <StringList values={result.repository.predicted_impact.files} emptyText="No affected files were predicted." />
          </Section>

          <Section title="Functions">
            <ComponentList components={result.impact.affected_functions} emptyText="No affected functions were predicted." />
          </Section>

          <Section title="Classes">
            <ComponentList components={result.impact.affected_classes} emptyText="No affected classes were predicted." />
          </Section>

          <Section title="APIs">
            <ComponentList components={result.impact.affected_apis} emptyText="No affected APIs were predicted." />
          </Section>

          <Section title="Tests">
            <ComponentList components={result.impact.affected_tests} emptyText="No affected tests were predicted." />
          </Section>

          <Section title="Dependency paths and reasons">
            <DependencyPathList paths={result.impact.dependency_paths} />
          </Section>

          <Section title="Risk indicators">
            {result.impact.risk_indicators.length === 0 ? (
              <Notice kind="empty" text="No risk indicators were reported." />
            ) : (
              <ul className="list">
                {result.impact.risk_indicators.map((risk) => (
                  <li key={`${risk.code}-${risk.file_id ?? 'global'}-${risk.detail}`}>
                    <strong>{risk.severity.toUpperCase()}</strong> · {risk.code} · {risk.detail}
                    {risk.file_id ? <div className="reason">File: {risk.file_id}</div> : null}
                    {risk.evidence ? <div className="reason">Evidence: {risk.evidence}</div> : null}
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </>
      )}
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

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  )
}

function StatusBadge({ tone, text }: { tone: 'ok' | 'warn' | 'error' | 'neutral'; text: string }) {
  return <span className={`badge badge-${tone}`}>{text}</span>
}

function Notice({ kind, text }: { kind: 'loading' | 'empty' | 'error'; text: string }) {
  return <div className={`notice notice-${kind}`}>{text}</div>
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <article className="stat">
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  )
}

function StringList({ values, emptyText }: { values: string[]; emptyText: string }) {
  if (!values.length) return <Notice kind="empty" text={emptyText} />
  return (
    <ul className="list">
      {values.map((value) => <li key={value}>{value}</li>)}
    </ul>
  )
}

function ComponentList({ components, emptyText }: { components: ImpactedComponent[]; emptyText: string }) {
  if (!components.length) return <Notice kind="empty" text={emptyText} />
  return (
    <ul className="list">
      {components.map((component) => (
        <li key={component.component_id}>
          <strong>{component.component_id}</strong>
          {component.reasons.length > 0 ? (
            <ul className="nested-list">
              {component.reasons.map((reason) => (
                <li key={`${component.component_id}-${reason}`} className="reason">{reason}</li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

function DependencyPathList({ paths }: { paths: DependencyPath[] }) {
  if (!paths.length) return <Notice kind="empty" text="No dependency paths were produced for this predicted impact." />

  return (
    <div className="path-list">
      {paths.map((path) => (
        <article className="path-item" key={`${path.source_id}-${path.target_id}-${path.node_ids.join('>')}`}>
          <header>
            <strong>{path.source_id}</strong>
            <span>to</span>
            <strong>{path.target_id}</strong>
          </header>
          <p className="reason">Nodes: {path.node_ids.join(' -> ')}</p>
          {path.steps.length > 0 ? (
            <ol className="steps">
              {path.steps.map((step, index) => (
                <li key={`${path.target_id}-${step.source_id}-${step.target_id}-${index}`}>
                  <span>{step.relationship}</span>
                  <div className="reason">{step.reason}</div>
                  <div className="reason">Evidence: {step.evidence}</div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="reason">Directly changed component.</p>
          )}
        </article>
      ))}
    </div>
  )
}
