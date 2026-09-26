"""FastAPI endpoints for CodeTwin's impact review workflow."""

from __future__ import annotations

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from codetwin.analysis_store import (
    create_analysis,
    execute_targeted_tests,
    get_analysis,
    get_analysis_context,
    submit_bob_review,
)
from codetwin.analyzer import InvalidAnalysisRequest
from codetwin.demo_service import create_payment_fix, create_payment_regression


class AnalyzeRequest(BaseModel):
    files: dict[str, str] = Field(min_length=1)
    changed_files: list[str] = Field(min_length=1)


class BobReviewRequest(BaseModel):
    confirmed_files: list[str]
    possible_files: list[str]
    not_affected_files: list[str]
    rationale: str = Field(min_length=1, max_length=5000)


def create_app(frontend_origins: str | None = None) -> FastAPI:
    app = FastAPI(title="CodeTwin API", version="0.1.0")
    configured_origins = frontend_origins
    if configured_origins is None:
        configured_origins = os.getenv("FRONTEND_ORIGINS", "")
    origins = [origin.strip() for origin in configured_origins.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/analyze")
    def analyze(request: AnalyzeRequest) -> dict[str, object]:
        try:
            return create_analysis(request.files, request.changed_files)
        except InvalidAnalysisRequest as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @app.get("/analyses/{analysis_id}")
    def analysis(analysis_id: str) -> dict[str, object]:
        result = get_analysis(analysis_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return result

    @app.get("/analyses/{analysis_id}/context")
    def analysis_context(analysis_id: str) -> dict[str, object]:
        result = get_analysis_context(analysis_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return result

    @app.post("/analyses/{analysis_id}/bob-review")
    def review(analysis_id: str, request: BobReviewRequest) -> dict[str, object]:
        try:
            result = submit_bob_review(
                analysis_id,
                request.confirmed_files,
                request.possible_files,
                request.not_affected_files,
                request.rationale,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return result

    @app.post("/analyses/{analysis_id}/run-tests")
    def run_tests(analysis_id: str) -> dict[str, object]:
        try:
            result = execute_targeted_tests(analysis_id)
        except (ValueError, InvalidAnalysisRequest) as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        if result is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return result

    @app.post("/demo/payment-regression")
    def payment_regression() -> dict[str, object]:
        try:
            return create_payment_regression()
        except (InvalidAnalysisRequest, FileNotFoundError) as error:
            raise HTTPException(status_code=500, detail="Payment regression demo could not be loaded") from error

    @app.post("/analyses/{analysis_id}/demo-fix")
    def payment_fix(analysis_id: str) -> dict[str, object]:
        try:
            result = create_payment_fix(analysis_id)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error
        except (InvalidAnalysisRequest, FileNotFoundError) as error:
            raise HTTPException(status_code=500, detail="Payment fix demo could not be applied") from error
        if result is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return result

    @app.get("/analyses")
    def analyses() -> dict[str, list[dict[str, object]]]:
        # Kept intentionally small: the prototype stores sessions in process memory.
        from codetwin.analysis_store import list_analyses

        return {"analyses": list_analyses()}

    return app


app = create_app()
