"""HTTP endpoints for generating plans from normalized LLM preferences."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.llm import LLMOutput
from app.schemas.planning import Plan, PlanningResultResponse
from app.service.planning_service import (
    NoFeasiblePlanError,
    NoPoisFoundError,
    UnsupportedTransportModeError,
    planning_service,
)

router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/{user_id}", response_model=PlanningResultResponse)
async def get_planning_result(user_id: UUID) -> PlanningResultResponse:
    result = planning_service.get_result(user_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nie znaleziono planowania dla tego użytkownika.",
        )
    return result


@router.post("", response_model=list[Plan], status_code=status.HTTP_200_OK)
async def create_plans(payload: LLMOutput) -> list[Plan]:
    try:
        return await planning_service.create_plans(payload)
    except NoPoisFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (NoFeasiblePlanError, UnsupportedTransportModeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
