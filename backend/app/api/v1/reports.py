from __future__ import annotations

import csv
import io
import json
from enum import Enum

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.application.reports.generate_reports_use_case import GenerateReportsUseCase
from app.core.rbac import require_any_authenticated_role
from app.infrastructure.repositories.city_repository import CityRepository
from app.infrastructure.repositories.forecast_repository import ForecastRepository
from app.infrastructure.repositories.optimization_repository import OptimizationRepository
from app.infrastructure.repositories.simulation_repository import SimulationRepository

router = APIRouter(prefix="/reports", tags=["reports"])


class ReportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"


def _use_case(session: AsyncSession) -> GenerateReportsUseCase:
    return GenerateReportsUseCase(
        city_repository=CityRepository(session),
        forecast_repository=ForecastRepository(session),
        optimization_repository=OptimizationRepository(session),
        simulation_repository=SimulationRepository(session),
    )


def _csv_response(filename: str, rows: list[dict]) -> Response:
    output = io.StringIO()
    if rows:
        fieldnames = list(rows[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    content = output.getvalue().encode("utf-8")
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/national")
async def get_national_report(
    format: ReportFormat = Query(default=ReportFormat.JSON),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_any_authenticated_role),
):
    payload = await _use_case(session).national_report()
    if format == ReportFormat.CSV:
        return _csv_response("national_report.csv", payload["rows"])
    return payload


@router.get("/city/{city_id}")
async def get_city_report(
    city_id: int,
    format: ReportFormat = Query(default=ReportFormat.JSON),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_any_authenticated_role),
):
    payload = await _use_case(session).city_report(city_id)
    if format == ReportFormat.CSV:
        row = {
            "city_id": payload["city"]["id"],
            "city_name": payload["city"]["name"],
            "state": payload["city"]["state"],
            "population": payload["city"]["population"],
            "latest_forecast": json.dumps(payload["latest_forecast"]),
            "latest_optimization": json.dumps(payload["latest_optimization"]),
            "grid_node_count": len(payload["grid_nodes"]),
            "transmission_line_count": len(payload["transmission_lines"]),
            "recent_simulation_count": len(payload["recent_simulations"]),
        }
        return _csv_response(f'city_report_{payload["city"]["name"].lower()}.csv', [row])
    return payload


@router.get("/forecast/{city_id}")
async def get_forecast_report(
    city_id: int,
    limit: int = Query(default=200, ge=1, le=5000),
    format: ReportFormat = Query(default=ReportFormat.JSON),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_any_authenticated_role),
):
    payload = await _use_case(session).forecast_report(city_id=city_id, limit=limit)
    if format == ReportFormat.CSV:
        return _csv_response(f'forecast_report_{payload["city_name"].lower()}.csv', payload["rows"])
    return payload


@router.get("/optimization/{city_id}")
async def get_optimization_report(
    city_id: int,
    limit: int = Query(default=200, ge=1, le=5000),
    format: ReportFormat = Query(default=ReportFormat.JSON),
    session: AsyncSession = Depends(get_session),
    _user=Depends(require_any_authenticated_role),
):
    payload = await _use_case(session).optimization_report(city_id=city_id, limit=limit)
    if format == ReportFormat.CSV:
        return _csv_response(f'optimization_report_{payload["city_name"].lower()}.csv', payload["rows"])
    return payload
