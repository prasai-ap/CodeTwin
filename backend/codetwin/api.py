"""HTTP interface for CodeTwin's deterministic analyzer."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from codetwin.analysis_store import create_analysis, get_analysis, submit_bob_review
from codetwin.analyzer import InvalidAnalysisRequest, analyze_repository


class AnalyzeRequest(BaseModel):
    files: dict[str, str] = Field(description="Repository snapshot as relative paths and UTF-8 source text")
    changed_files: list[str] = Field(min_length=1, description="Changed Python files in the proposed change")


class BobReviewRequest(BaseModel):
    confirmed_files: list[str]
    possible_files: list[str]
    not_affected_files: list[str]
    rationale: str = Field(min_length=1)


app = FastAPI(
    title="CodeTwin API",
    version="0.1.0",
    description="Deterministic Python dependency and impact analysis.",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict[str, object]:
    try:
        return analyze_repository(request.files, request.changed_files)
    except InvalidAnalysisRequest as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/analyses")
def create_analysis_session(request: AnalyzeRequest) -> dict[str, object]:
    try:
        return create_analysis(request.files, request.changed_files)
    except InvalidAnalysisRequest as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/analyses/{analysis_id}")
def read_analysis(analysis_id: str) -> dict[str, object]:
    analysis = get_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@app.post("/analyses/{analysis_id}/bob-review")
def record_bob_review(analysis_id: str, request: BobReviewRequest) -> dict[str, object]:
    try:
        analysis = submit_bob_review(
            analysis_id,
            request.confirmed_files,
            request.possible_files,
            request.not_affected_files,
            request.rationale,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis
