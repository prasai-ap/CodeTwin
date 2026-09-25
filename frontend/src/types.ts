export interface DependencyEdge {
  source: string;
  target: string;
}

export interface PredictedImpact {
  files: string[];
  tests: string[];
  api_files: string[];
  components: string[];
}

export interface FileAssessment {
  prediction: 'predicted_impact' | 'not_predicted';
  bob_assessment: 'bob_confirmed_impact' | 'possible_impact' | 'not_affected';
}

export interface BobReview {
  status: 'complete';
  bob_confirmed_impact: string[];
  possible_impact: string[];
  not_affected: string[];
  rationale: string;
  file_assessments: Record<string, FileAssessment>;
}

export interface TestResult {
  file: string;
  runner: 'pytest' | 'unittest';
  status: 'passed' | 'failed' | 'error' | 'timeout';
  exit_code: number | null;
  output: string;
}

export interface TestResults {
  status: 'not_run' | 'passed' | 'failed' | 'error' | 'timeout' | 'no_tests';
  passed: boolean;
  targeted_tests?: string[];
  results?: TestResult[];
}

export type AnalysisStatus =
  | 'awaiting_bob_review'
  | 'awaiting_tests'
  | 'safe_to_merge'
  | 'regression_detected'
  | 'possible_impact_unresolved'
  | 'analysis_errors'
  | 'test_execution_error'
  | 'no_targeted_tests';

export interface AnalysisReport {
  analysis_id: string;
  demo_scenario?: string;
  parent_analysis_id?: string;
  status: AnalysisStatus;
  changed_files: string[];
  predicted_impact: PredictedImpact;
  not_affected: string[];
  dependency_edges: DependencyEdge[];
  parse_errors: { file: string; message: string }[];
  bob_review: BobReview | null;
  test_results: TestResults;
  safe_to_merge: boolean;
}
