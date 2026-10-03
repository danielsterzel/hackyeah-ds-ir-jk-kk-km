"""HTTP endpoints for generating plans from normalized LLM preferences."""

from fastapi import APIRouter, HTTPException, status

from app.schemas.llm import LLMOutput
from app.schemas.planning import Plan
from app.service.planning_service import (
    NoFeasiblePlanError,
    NoPoisFoundError,
    UnsupportedTransportModeError,
    planning_service,
)

router = APIRouter(prefix="/planning", tags=["planning"])


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
