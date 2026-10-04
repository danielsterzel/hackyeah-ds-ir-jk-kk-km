import asyncio
import json
import logging
import uuid
from collections import deque
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import get_args

from ollama import chat, AsyncClient
from pydantic import ValidationError

from app.core.settings import settings
from app.schemas.llm import LLMOutput, PlaceCategory, UserInitQuestionnaire

SERVICE_DIRECTORY = Path(__file__).resolve().parent
QUESTIONS_FILEPATH = SERVICE_DIRECTORY / "questions.txt"
PROMPT_FILEPATH = SERVICE_DIRECTORY / "new_prompt.txt"
# MODEL = "qwen3:30b"
MODEL = "gpt-oss:120b"
DEFAULT_KRAKOW_LOCATION = {
    "latitude": 50.0614,
    "longitude": 19.9372,
}

questions = QUESTIONS_FILEPATH.read_text(encoding="utf-8").strip().splitlines()
prompt = PROMPT_FILEPATH.read_text(encoding="utf-8").strip()

CATEGORY_EXPANSIONS: dict[PlaceCategory, set[PlaceCategory]] = {
    "castle": {"historic", "architecture"},
    "concert": {"music"},
    "forest": {"nature"},
    "garden": {"nature"},
    "monument": {"historic"},
    "religious": {"historic", "architecture"},
}

client = AsyncClient(
    host="https://ollama.com",
    headers={
        "Authorization": f"Bearer {settings.ollama_api_key}"
    }
)
logger = logging.getLogger(__name__)

def expand_categories(
    preferred: list[PlaceCategory],
    excluded: list[PlaceCategory],
) -> list[PlaceCategory]:
    result: set[PlaceCategory] = set(preferred)

    for category in preferred:
        result.update(CATEGORY_EXPANSIONS.get(category, set()))

    result.difference_update(excluded)

    return sorted(result)


def normalize_llm_payload(content: str) -> dict:
    payload = json.loads(content)

    aliases = {
        "startDateTime": "startAt",
        "endDateTime": "endAt",
    }
    for source, target in aliases.items():
        if target not in payload and source in payload:
            payload[target] = payload[source]

    if "transportModes" not in payload and "travelMode" in payload:
        payload["transportModes"] = [payload["travelMode"]]

    transport_aliases = {
        "walk": "walking",
        "bike": "bicycle",
        "public transit": "public_transport",
        "transit": "public_transport",
    }
    payload["transportModes"] = [
        transport_aliases.get(mode, mode)
        for mode in payload.get("transportModes", [])
    ]
    return payload


class OllamaService:

    def __init__(self):
        self.prompt = prompt
        self.questions = deque(questions)
        self.user_metadata: UserInitQuestionnaire | None = None

        self.messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": self.prompt,
            }
        ]

    async def init_conversation(self, user_metadata: UserInitQuestionnaire):
        self.user_metadata = user_metadata.model_copy(
            update={
                "latitude": DEFAULT_KRAKOW_LOCATION["latitude"],
                "longitude": DEFAULT_KRAKOW_LOCATION["longitude"],
            }
        )
        context = {
            "current_datetime": datetime.now().astimezone().isoformat(),
            "timezone": "Europe/Warsaw",
            "location": {
                "latitude": self.user_metadata.latitude,
                "longitude": self.user_metadata.longitude,
            },
            "optimization_strategy": user_metadata.optimization_strategy,
            "allowed_place_categories": list(get_args(PlaceCategory)),
        }

        self.messages.append(
            {
                "role": "user",
                "content": f"APPLICATION CONTEXT:\n{context}",
            }
        )

    async def ask_question(self) -> str | None:
        if not self.questions:
            return None

        question = self.questions.popleft()

        self.messages.append(
            {
                "role": "assistant",
                "content": question,
            }
        )

        return question

    async def answer_response(self, answer: str):
        self.messages.append(
            {
                "role": "user",
                "content": answer,
            }
        )

    async def converse(self, user_metadata: UserInitQuestionnaire):

        await self.init_conversation(user_metadata=user_metadata)
        while self.questions:
            question = await self.ask_question()

            print(question)

            user_answer = input("> ")

            await self.answer_response(user_answer)

        stream = await client.chat(
            model=MODEL,
            messages=self.messages,
            stream=True,
            format=LLMOutput.model_json_schema(),
            think=False,
            keep_alive="1m",
            options={"temperature": 0},
        )

        final_content = ""
        async for chunk in stream:
            content = chunk.message.content

            if content:
                print(content, end="", flush=True)
                final_content += content

        output = LLMOutput.model_validate_json(final_content)

        output.preferred_categories = expand_categories(
            output.preferred_categories,
            output.excluded_categories,
        )

        return output

    async def finalize(self) -> LLMOutput:
        last_content = ""
        for attempt in range(2):
            try:
                response = await client.chat(
                    model=MODEL,
                    messages=self.messages,
                    format=LLMOutput.model_json_schema(),
                    think=False,
                    options={"temperature": 0},
                    keep_alive="1m",
                )
            except Exception:
                logger.exception(
                    "Questionnaire LLM request failed: attempt=%d model=%s messages=%d",
                    attempt + 1,
                    MODEL,
                    len(self.messages),
                )
                raise

            content = response.message.content
            last_content = content
            logger.error(
                "Questionnaire LLM raw response: attempt=%d model=%s content=%s",
                attempt + 1,
                MODEL,
                content,
            )

            try:
                payload = normalize_llm_payload(content)
                output = LLMOutput.model_validate(payload)
                break
            except (ValidationError, ValueError):
                if attempt == 1:
                    logger.exception(
                        "Questionnaire LLM response validation failed after retry: "
                        "model=%s raw_response=%s",
                        MODEL,
                        content,
                    )
                    break

                logger.warning(
                    "Questionnaire LLM returned an incomplete schema; retrying with "
                    "an explicit full-output instruction: %s",
                    content,
                )
                self.messages.append(
                    {
                        "role": "user",
                        "content": (
                            "Your previous JSON was incomplete and is invalid. "
                            "Return a new JSON object containing every required "
                            "LLMOutput field: startAt, endAt, startLocation, "
                            "endLocation, preferredCategories, excludedCategories, "
                            "foodPreferences, transportModes, avoidCrowds, "
                            "weatherSensitive, and optimizationStrategy. "
                            "Use the application context for startLocation and "
                            "optimizationStrategy. Do not omit fields."
                        ),
                    }
                )
        else:
            raise RuntimeError("Questionnaire LLM produced no output")

        if "output" not in locals():
            output = self._fallback_output(last_content)

        output.preferred_categories = expand_categories(
            preferred=output.preferred_categories,
            excluded=output.excluded_categories,
        )

        return output

    def _fallback_output(self, raw_response: str) -> LLMOutput:
        if self.user_metadata is None:
            raise RuntimeError("Questionnaire metadata is missing")

        now = datetime.now().astimezone()
        tomorrow = now.date() + timedelta(days=1)
        logger.warning(
            "Using questionnaire defaults after invalid LLM response: %s",
            raw_response,
        )
        return LLMOutput(
            start_at=datetime.combine(tomorrow, time(9), tzinfo=now.tzinfo),
            end_at=datetime.combine(tomorrow, time(18), tzinfo=now.tzinfo),
            start_location={
                "latitude": self.user_metadata.latitude,
                "longitude": self.user_metadata.longitude,
            },
            end_location=None,
            preferred_categories=[],
            food_preferences=[],
            transport_modes=["walking"],
            avoid_crowds=False,
            weather_sensitive=False,
            optimization_strategy=self.user_metadata.optimization_strategy,
            excluded_categories=[],
        )


async def main():
    service = OllamaService()
    user_metadata = UserInitQuestionnaire(
        latitude=27.5,
        longitude=58.3,
        optimization_strategy="cheapest",
        id=uuid.uuid4(),
    )
    result = await service.converse(user_metadata)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
