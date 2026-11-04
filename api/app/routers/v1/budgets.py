from fastapi import APIRouter
from pydantic import BaseModel

from app.domain.models import BudgetScenario
from app.services.calculation_service import CalculationService

router = APIRouter(prefix="/budgets", tags=["Budgets & Scenarios"])


class BudgetComparisonRequest(BaseModel):
    scenario_a: BudgetScenario
    scenario_b: BudgetScenario


@router.post("/compare")
async def compare_budgets(request: BudgetComparisonRequest):
    return CalculationService.compare_budget_scenarios(
        scenario_a=request.scenario_a,
        scenario_b=request.scenario_b,
    )
