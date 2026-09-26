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

export type ImpactEdge = {
  source: string
  target: string
  kind: string
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
