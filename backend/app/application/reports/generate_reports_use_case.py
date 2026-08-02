from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.domain.exceptions import CityNotFoundError
from app.infrastructure.repositories.city_repository import CityRepository
from app.infrastructure.repositories.forecast_repository import ForecastRepository
from app.infrastructure.repositories.optimization_repository import OptimizationRepository
from app.infrastructure.repositories.simulation_repository import SimulationRepository
from app.quantum.grid_metrics import compute_co2_reduction_pct


def _renewable_pct(decoded: dict) -> float:
    renewable = decoded.get("hydro_mw", 0) + decoded.get("wind_mw", 0) + decoded.get("solar_mw", 0)
    total = decoded.get("total_supply_mw", 0)
    if total <= 0:
        return 0.0
    return round(100 * renewable / total, 2)


@dataclass
class GenerateReportsUseCase:
    city_repository: CityRepository
    forecast_repository: ForecastRepository
    optimization_repository: OptimizationRepository
    simulation_repository: SimulationRepository

    async def national_report(self) -> dict:
        cities = await self.city_repository.list_all()
        rows: list[dict] = []

        for city in cities:
            latest_forecast = await self.forecast_repository.get_latest_for_city(city.id)
            latest_optimization = await self.optimization_repository.get_latest_for_city(city.id)

            row: dict = {
                "city_id": city.id,
                "city_name": city.name,
                "state": city.state,
                "latest_forecast_mw": float(latest_forecast.predicted_mw) if latest_forecast else None,
                "latest_forecast_target_date": str(latest_forecast.target_date) if latest_forecast else None,
                "latest_optimization_score": float(latest_optimization.optimization_score)
                if latest_optimization
                else None,
                "latest_grid_stability_score": float(latest_optimization.grid_stability_score)
                if latest_optimization and latest_optimization.grid_stability_score is not None
                else None,
                "latest_cost_reduction_pct": float(latest_optimization.cost_reduction_pct)
                if latest_optimization and latest_optimization.cost_reduction_pct is not None
                else None,
                "latest_power_loss_reduction_pct": float(latest_optimization.power_loss_reduction_pct)
                if latest_optimization and latest_optimization.power_loss_reduction_pct is not None
                else None,
                "latest_co2_reduction_pct": compute_co2_reduction_pct(latest_optimization.allocation_result)
                if latest_optimization
                else None,
                "latest_renewable_pct": _renewable_pct(latest_optimization.allocation_result)
                if latest_optimization
                else None,
            }
            rows.append(row)

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "report_type": "national",
            "total_cities": len(cities),
            "rows": rows,
        }

    async def city_report(self, city_id: int) -> dict:
        city = await self.city_repository.get_by_id(city_id)
        if city is None:
            raise CityNotFoundError(f"City with id {city_id} was not found")

        nodes = await self.city_repository.get_nodes_for_city(city_id)
        lines = await self.city_repository.get_transmission_lines_for_nodes([n.id for n in nodes])
        latest_forecast = await self.forecast_repository.get_latest_for_city(city_id)
        latest_optimization = await self.optimization_repository.get_latest_for_city(city_id)
        simulation_history = await self.simulation_repository.get_history_for_city(city_id, limit=20)

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "report_type": "city",
            "city": {
                "id": city.id,
                "name": city.name,
                "state": city.state,
                "population": city.population,
                "latitude": float(city.latitude),
                "longitude": float(city.longitude),
                "timezone": city.timezone,
            },
            "grid_nodes": [
                {
                    "node_id": n.id,
                    "node_code": n.node_code,
                    "status": n.status,
                    "transmission_capacity_mw": float(n.transmission_capacity_mw),
                }
                for n in nodes
            ],
            "transmission_lines": [
                {
                    "line_id": l.id,
                    "from_node_id": l.from_node_id,
                    "to_node_id": l.to_node_id,
                    "status": l.status,
                    "capacity_mw": float(l.capacity_mw),
                    "current_load_mw": float(l.current_load_mw),
                    "utilization_pct": round(
                        100 * float(l.current_load_mw) / float(l.capacity_mw), 2
                    )
                    if float(l.capacity_mw) > 0
                    else 0.0,
                }
                for l in lines
            ],
            "latest_forecast": {
                "predicted_mw": float(latest_forecast.predicted_mw),
                "as_of_date": str(latest_forecast.as_of_date),
                "target_date": str(latest_forecast.target_date),
                "horizon": latest_forecast.horizon,
                "model_version": latest_forecast.model_version,
            }
            if latest_forecast
            else None,
            "latest_optimization": {
                "run_id": latest_optimization.id,
                "run_at": latest_optimization.run_at.isoformat(),
                "optimization_score": float(latest_optimization.optimization_score),
                "cost_reduction_pct": float(latest_optimization.cost_reduction_pct)
                if latest_optimization.cost_reduction_pct is not None
                else None,
                "power_loss_reduction_pct": float(latest_optimization.power_loss_reduction_pct)
                if latest_optimization.power_loss_reduction_pct is not None
                else None,
                "grid_stability_score": float(latest_optimization.grid_stability_score)
                if latest_optimization.grid_stability_score is not None
                else None,
                "allocation_result": latest_optimization.allocation_result,
            }
            if latest_optimization
            else None,
            "recent_simulations": [
                {
                    "run_id": s.id,
                    "scenario_type": s.scenario_type,
                    "scenario_name": s.scenario_name,
                    "as_of_date": s.as_of_date,
                    "run_at": s.run_at.isoformat(),
                }
                for s in simulation_history
            ],
        }

    async def forecast_report(self, city_id: int, limit: int = 200) -> dict:
        city = await self.city_repository.get_by_id(city_id)
        if city is None:
            raise CityNotFoundError(f"City with id {city_id} was not found")

        history = await self.forecast_repository.get_history_for_city(city_id, limit=limit)
        rows = [
            {
                "forecast_id": r.id,
                "city_id": r.city_id,
                "city_name": city.name,
                "horizon": r.horizon,
                "as_of_date": str(r.as_of_date),
                "target_date": str(r.target_date),
                "predicted_mw": float(r.predicted_mw),
                "model_version": r.model_version,
                "created_at": r.created_at.isoformat(),
            }
            for r in history
        ]

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "report_type": "forecast",
            "city_id": city.id,
            "city_name": city.name,
            "rows": rows,
        }

    async def optimization_report(self, city_id: int, limit: int = 200) -> dict:
        city = await self.city_repository.get_by_id(city_id)
        if city is None:
            raise CityNotFoundError(f"City with id {city_id} was not found")

        history = await self.optimization_repository.get_history_for_city(city_id, limit=limit)
        rows = [
            {
                "run_id": r.id,
                "city_id": r.city_id,
                "city_name": city.name,
                "algorithm": r.algorithm,
                "run_at": r.run_at.isoformat(),
                "iterations": r.iterations,
                "optimization_score": float(r.optimization_score),
                "cost_reduction_pct": float(r.cost_reduction_pct)
                if r.cost_reduction_pct is not None
                else None,
                "power_loss_reduction_pct": float(r.power_loss_reduction_pct)
                if r.power_loss_reduction_pct is not None
                else None,
                "grid_stability_score": float(r.grid_stability_score)
                if r.grid_stability_score is not None
                else None,
                "execution_time_ms": r.execution_time_ms,
                "objective_gap": float(r.objective_gap),
                "matched_classical_optimum": r.matched_classical_optimum,
                "target_demand_mw": float(r.allocation_result.get("target_demand_mw", 0)),
                "total_supply_mw": float(r.allocation_result.get("total_supply_mw", 0)),
                "mismatch_mw": float(r.allocation_result.get("mismatch_mw", 0)),
                "renewable_pct": _renewable_pct(r.allocation_result),
                "co2_reduction_pct": compute_co2_reduction_pct(r.allocation_result),
            }
            for r in history
        ]

        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "report_type": "optimization",
            "city_id": city.id,
            "city_name": city.name,
            "rows": rows,
        }
