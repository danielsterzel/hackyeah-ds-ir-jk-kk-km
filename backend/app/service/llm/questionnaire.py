import asyncio
import json
import logging
import uuid
from collections import deque
from datetime import datetime
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
        self.user_metadata = user_metadata
        context = {
            "current_datetime": datetime.now().astimezone().isoformat(),
            "timezone": "Europe/Warsaw",
            "location": {
                "latitude": user_metadata.latitude,
                "longitude": user_metadata.longitude,
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

        output = self._parse_output(final_content)

        output.preferred_categories = expand_categories(
            output.preferred_categories,
            output.excluded_categories,
        )

        return output

    async def finalize(self) -> LLMOutput:
        if self.user_metadata is None:
            raise RuntimeError("Questionnaire metadata is not initialized")

        response = await self._finalize_request()
        content = response.message.content or ""

        if not content.strip():
            logger.warning(
                "LLM returned empty content during questionnaire finalization "
                "(done_reason=%s, thinking_length=%s)",
                response.done_reason,
                len(response.message.thinking or ""),
            )
            self.messages.append(
                {
                    "role": "user",
                    "content": (
                        "Return only the final questionnaire result as one valid "
                        "JSON object. Do not return an empty response or reasoning."
                    ),
                }
            )
            response = await self._finalize_request()
            content = response.message.content or ""

        try:
            output = self._parse_output(content)
        except ValueError as first_error:
            self.messages.append(
                {
                    "role": "user",
                    "content": (
                        "Your previous JSON was incomplete. Return the complete "
                        "questionnaire result again as exactly one JSON object. "
                        "Include every required field: startAt, endAt, "
                        "startLocation, endLocation, preferredCategories, "
                        "foodPreferences, transportModes, avoidCrowds, "
                        "weatherSensitive, optimizationStrategy, and "
                        "excludedCategories. Derive dates and times from the "
                        "full questionnaire transcript; do not omit them. "
                        f"Validation issue: {first_error}"
                    ),
                }
            )
            retry_response = await self._finalize_request()
            retry_content = retry_response.message.content or ""
            output = self._parse_output(retry_content)

        output.preferred_categories = expand_categories(
            preferred=output.preferred_categories,
            excluded=output.excluded_categories,
        )

        return output

    async def _finalize_request(self):
        return await client.chat(
            model=MODEL,
            messages=self.messages,
            format=LLMOutput.model_json_schema(),
            think=False,
            options={"temperature": 0},
        )

    def _parse_output(self, content: str) -> LLMOutput:
        try:
            raw_output = json.loads(content)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ValueError("LLM returned invalid JSON") from exc

        if not isinstance(raw_output, dict):
            raise ValueError("LLM returned JSON, but not a JSON object")

        self._normalize_output(raw_output)

        try:
            return LLMOutput.model_validate(raw_output)
        except ValidationError as exc:
            raise ValueError(
                f"LLM returned an incomplete or invalid questionnaire output: {exc}"
            ) from exc

    def _normalize_output(self, raw_output: dict[str, object]) -> None:
        """Fill only values that are authoritative in application context."""
        if self.user_metadata is None:
            raise RuntimeError("Questionnaire metadata is not initialized")

        crowd_preference = raw_output.pop("crowdPreference", None)
        if "avoidCrowds" not in raw_output and isinstance(crowd_preference, str):
            raw_output["avoidCrowds"] = crowd_preference.lower() in {
                "low",
                "avoid",
                "quiet",
            }

        aliases = {
            "transportMode": "transportModes",
            "weatherPreference": "weatherSensitive",
            "weatherMatters": "weatherSensitive",
        }
        for alias, field_name in aliases.items():
            if field_name not in raw_output and alias in raw_output:
                raw_output[field_name] = raw_output.pop(alias)

        raw_output.setdefault("transportModes", [])
        raw_output.setdefault("avoidCrowds", False)
        raw_output.setdefault("weatherSensitive", False)
        raw_output.setdefault(
            "startLocation",
            {
                "latitude": self.user_metadata.latitude,
                "longitude": self.user_metadata.longitude,
            },
        )
        raw_output.setdefault(
            "optimizationStrategy",
            self.user_metadata.optimization_strategy,
        )
        raw_output.setdefault("endLocation", None)


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
