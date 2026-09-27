"""FastAPI endpoints for CodeTwin's impact review workflow."""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from codetwin.analysis_store import (
    create_analysis,
    execute_targeted_tests,
    get_analysis,
    get_analysis_context,
    submit_bob_review,
)
from codetwin.analyzer import InvalidAnalysisRequest
from codetwin.analyzer import analyze_repository as run_repository_analysis
from codetwin.demo_service import create_payment_fix, create_payment_regression
from codetwin.impact_engine import InvalidImpactRequest, ProposedChange, predict_impact
from codetwin.repository_graph import build_repository_graph, normalize_path


logger = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    files: dict[str, str] = Field(min_length=1)
    changed_files: list[str] = Field(min_length=1)


class AnalyzeRepositoryRequest(BaseModel):
    files: dict[str, str] = Field(min_length=1)
    changed_files: list[str]


class AnalyzeImpactRequest(BaseModel):
    files: dict[str, str] = Field(min_length=1)
    component_kind: Literal["file", "module", "function", "class", "api_endpoint", "test"]
    component_id: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=5000)


class ErrorResponse(BaseModel):
    status: Literal["error"]
    error_code: str
    detail: str


class AnalyzeRepositoryResponse(BaseModel):
    status: Literal["success"]
    changed_files: list[str]
    predicted_impact: dict[str, Any]
    not_affected: list[str]
    dependency_edges: list[dict[str, Any]]
    function_edges: list[dict[str, Any]]
    parse_errors: list[dict[str, Any]]
    analysis_limitations: list[dict[str, Any]]


class AnalyzeImpactResponse(BaseModel):
    status: Literal["success"]
    proposed_change: dict[str, Any]
    affected_files: list[dict[str, Any]]
    affected_modules: list[dict[str, Any]]
    affected_functions: list[dict[str, Any]]
    affected_classes: list[dict[str, Any]]
    affected_apis: list[dict[str, Any]]
    affected_tests: list[dict[str, Any]]
    dependency_paths: list[dict[str, Any]]
    risk_indicators: list[dict[str, Any]]


class BobReviewRequest(BaseModel):
    confirmed_files: list[str]
    possible_files: list[str]
    not_affected_files: list[str]
    rationale: str = Field(min_length=1, max_length=5000)


def _normalize_snapshot(files: dict[str, str]) -> dict[str, str]:
    normalized_files: dict[str, str] = {}
    for original_path, source in files.items():
        path = normalize_path(original_path)
        if path in normalized_files:
            raise InvalidAnalysisRequest(f"Duplicate normalized repository path: {path}")
        normalized_files[path] = source
    return normalized_files


def _error_response(status_code: int, error_code: str, detail: str) -> JSONResponse:
    payload = ErrorResponse(status="error", error_code=error_code, detail=detail)
    return JSONResponse(status_code=status_code, content=payload.model_dump())


def create_app(frontend_origins: str | None = None, demo_only: bool | None = None) -> FastAPI:
    app = FastAPI(title="CodeTwin API", version="0.1.0")
    if demo_only is None:
        demo_only = os.getenv("CODETWIN_DEMO_ONLY", "").strip().lower() in {"1", "true", "yes"}
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

    @app.post(
        "/analyze-repository",
        response_model=AnalyzeRepositoryResponse | ErrorResponse,
    )
    def analyze_repository_endpoint(request: AnalyzeRepositoryRequest) -> AnalyzeRepositoryResponse | ErrorResponse:
        logger.info(
            "Repository analysis requested",
            extra={
                "file_count": len(request.files),
                "changed_file_count": len(request.changed_files),
            },
        )
        try:
            normalized_files = _normalize_snapshot(request.files)
            report = run_repository_analysis(normalized_files, request.changed_files)
        except InvalidAnalysisRequest as error:
            logger.warning("Repository analysis rejected: %s", error)
            return _error_response(422, "invalid_repository_analysis_request", str(error))
        except Exception:
            logger.exception("Repository analysis failed unexpectedly")
            return _error_response(500, "repository_analysis_failed", "Repository analysis failed")

        logger.info(
            "Repository analysis completed",
            extra={"impacted_file_count": len(report["predicted_impact"]["files"])},
        )
        return AnalyzeRepositoryResponse(status="success", **report)

    @app.post(
        "/analyze-impact",
        response_model=AnalyzeImpactResponse | ErrorResponse,
    )
    def analyze_impact_endpoint(request: AnalyzeImpactRequest) -> AnalyzeImpactResponse | ErrorResponse:
        logger.info(
            "Impact analysis requested",
            extra={"component_kind": request.component_kind, "component_id": request.component_id},
        )
        try:
            normalized_files = _normalize_snapshot(request.files)
            graph = build_repository_graph(normalized_files)
            proposed_change = ProposedChange(
                component_kind=request.component_kind,
                component_id=request.component_id,
                description=request.description,
            )
            prediction = predict_impact(graph, proposed_change).to_dict()
        except InvalidAnalysisRequest as error:
            logger.warning("Impact analysis repository validation failed: %s", error)
            return _error_response(422, "invalid_repository_snapshot", str(error))
        except InvalidImpactRequest as error:
            logger.warning("Impact analysis rejected: %s", error)
            return _error_response(422, "invalid_impact_request", str(error))
        except Exception:
            logger.exception("Impact analysis failed unexpectedly")
            return _error_response(500, "impact_analysis_failed", "Impact analysis failed")

        logger.info(
            "Impact analysis completed",
            extra={
                "affected_function_count": len(prediction["affected_functions"]),
                "affected_test_count": len(prediction["affected_tests"]),
            },
        )
        return AnalyzeImpactResponse(status="success", **prediction)

    @app.post("/analyze")
    def analyze(request: AnalyzeRequest) -> dict[str, object]:
        if demo_only:
            raise HTTPException(
                status_code=403,
                detail="Generic repository analysis is disabled on the public synthetic demo service",
            )
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
        if demo_only:
            current = get_analysis(analysis_id)
            scenario = current.get("demo_scenario") if current else None
            if not isinstance(scenario, dict) or scenario.get("name") not in {
                "payment_authorization_regression",
                "payment_authorization_regression_fixed",
            }:
                raise HTTPException(
                    status_code=403,
                    detail="The public demo executes tests only for its built-in synthetic payment scenario",
                )
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
