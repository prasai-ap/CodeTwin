"""HTTP interface for CodeTwin's deterministic analyzer."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from codetwin.analyzer import InvalidAnalysisRequest, analyze_repository


class AnalyzeRequest(BaseModel):
    files: dict[str, str] = Field(description="Repository snapshot as relative paths and UTF-8 source text")
    changed_files: list[str] = Field(min_length=1, description="Changed Python files in the proposed change")


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
