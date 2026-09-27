export type ApiRoute = {
  file: string
  method: string
  path: string
  handler: string
}

export type ImpactFunction = {
  file: string
  qualname: string
  line: number
  owner: string | null
  id: string
}

export type ImpactClass = {
  file: string
  qualname: string
  line: number
  id: string
}

export type ImpactEdge = {
  source: string
  target: string
  kind: string
  reason?: string
  evidence?: string
  line?: number | null
}

export type FileAssessment = {
  prediction: 'predicted_impact' | 'not_predicted'
  bob_assessment: 'bob_confirmed_impact' | 'possible_impact' | 'not_affected'
}

export type BobReview = {
  status: 'complete'
  bob_confirmed_impact: string[]
  possible_impact: string[]
  not_affected: string[]
  rationale: string
  file_assessments: Record<string, FileAssessment>
}

export type TestResultFile = {
  file: string
  runner: 'pytest' | 'unittest'
  status: 'passed' | 'failed' | 'error' | 'timeout'
  exit_code: number | null
  output: string
}

export type TestResults = {
  status: 'not_run' | 'passed' | 'failed' | 'error' | 'timeout' | 'no_tests'
  passed: boolean
  targeted_tests: string[]
  results: TestResultFile[]
}

export type AnalysisStatus =
  | 'awaiting_bob_review'
  | 'awaiting_tests'
  | 'safe_to_merge'
  | 'regression_detected'
  | 'possible_impact_unresolved'
  | 'analysis_errors'
  | 'test_execution_error'
  | 'no_targeted_tests'

export type Analysis = {
  analysis_id: string
  status: AnalysisStatus
  changed_files: string[]
  predicted_impact: {
    files: string[]
    functions: ImpactFunction[]
    classes: ImpactClass[]
    tests: string[]
    api_files: string[]
    api_routes: ApiRoute[]
    components: string[]
  }
  not_affected: string[]
  dependency_edges: ImpactEdge[]
  function_edges: ImpactEdge[]
  parse_errors: { file: string; message: string }[]
  bob_review: BobReview | null
  test_results: TestResults
  safe_to_merge: boolean
  demo_scenario?: {
    name: string
    description: string
    parent_analysis_id: string | null
  }
}

export type ImpactNodeStatus = 'changed' | 'predicted' | 'confirmed' | 'possible' | 'not_affected'

export type ApiError = {
  status: 'error'
  error_code: string
  detail: string
}

export type AnalyzeRepositoryRequest = {
  files: Record<string, string>
  changed_files: string[]
}

export type RepositoryAnalysisResult = {
  status: 'success'
  changed_files: string[]
  predicted_impact: {
    files: string[]
    functions: ImpactFunction[]
    classes: ImpactClass[]
    tests: string[]
    api_files: string[]
    api_routes: ApiRoute[]
    components: string[]
  }
  not_affected: string[]
  dependency_edges: ImpactEdge[]
  function_edges: ImpactEdge[]
  parse_errors: { file: string; message: string | null }[]
  analysis_limitations: Array<{
    file_id: string
    kind: string
    detail: string
    line: number | null
    evidence: string | null
  }>
}

export type AnalyzeImpactRequest = {
  files: Record<string, string>
  component_kind: 'file' | 'module' | 'function' | 'class' | 'api_endpoint' | 'test'
  component_id: string
  description: string
}

export type DependencyPathStep = {
  source_id: string
  target_id: string
  relationship: string
  reason: string
  evidence: string
  line: number | null
  label: string
}

export type DependencyPath = {
  label: string
  source_id: string
  target_id: string
  node_ids: string[]
  steps: DependencyPathStep[]
}

export type ImpactedComponent = {
  label: string
  component_kind: string
  component_id: string
  reasons: string[]
  dependency_path: DependencyPath
}

export type ImpactAnalysisResult = {
  status: 'success'
  proposed_change: {
    component_kind: string
    component_id: string
    description: string
  }
  affected_files: ImpactedComponent[]
  affected_modules: ImpactedComponent[]
  affected_functions: ImpactedComponent[]
  affected_classes: ImpactedComponent[]
  affected_apis: ImpactedComponent[]
  affected_tests: ImpactedComponent[]
  dependency_paths: DependencyPath[]
  risk_indicators: Array<{
    label: string
    code: string
    severity: string
    detail: string
    file_id: string | null
    evidence: string | null
  }>
}

export type GraphSnapshot = {
  analysis_id?: string
  changed_files: string[]
  predicted_impact: {
    files: string[]
  }
  dependency_edges: ImpactEdge[]
  function_edges: ImpactEdge[]
  bob_review?: BobReview | null
}
