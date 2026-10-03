from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, status

from app.schemas.llm import (
    LLMOutput,
    LLMQuestion,
    UserAnswer,
    UserInitQuestionnaire,
)
from app.service.llm.questionnaire import OllamaService

router = APIRouter(
    prefix="/questionnaire",
    tags=["questionnaire"],
)

services: dict[UUID, OllamaService] = {}
questionnaire_results: dict[UUID, LLMOutput] = {}


async def finalize_questionnaire(
    user_id: UUID,
    service: OllamaService,
) -> None:
    questionnaire_results[user_id] = await service.finalize()


@router.post("/init", response_model=LLMQuestion)
async def init_questionnaire(
    data: UserInitQuestionnaire,
) -> LLMQuestion:
    service = OllamaService()
    services[data.id] = service

    await service.init_conversation(data)

    question = await service.ask_question()

    if question is None:
        raise HTTPException(
            status_code=500,
            detail="No questionnaire questions configured",
        )

    return LLMQuestion(question=question)


@router.post(
    "/answer",
    response_model=LLMQuestion,
    responses={204: {"description": "Questionnaire completed"}},
)
async def answer_question(
    data: UserAnswer,
    background_tasks: BackgroundTasks,
) -> LLMQuestion | Response:
    service = services.get(data.id)

    if service is None:
        raise HTTPException(
            status_code=400,
            detail="Questionnaire not initialized",
        )

    await service.answer_response(data.answer)

    question = await service.ask_question()

    if question is not None:
        return LLMQuestion(question=question)

    services.pop(data.id, None)
    background_tasks.add_task(finalize_questionnaire, data.id, service)

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
        background=background_tasks,
    )
