import asyncio
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import get_args

from ollama import chat, AsyncClient

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

        self.messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": self.prompt,
            }
        ]

    async def init_conversation(self, user_metadata: UserInitQuestionnaire):
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

        output = LLMOutput.model_validate_json(final_content)

        output.preferred_categories = expand_categories(
            output.preferred_categories,
            output.excluded_categories,
        )

        return output

    async def finalize(self) -> LLMOutput:
        response = await client.chat(
            model=MODEL,
            messages=self.messages,
            format=LLMOutput.model_json_schema(),
            think=False,
        )

        output = LLMOutput.model_validate_json(response.message.content)

        output.preferred_categories = expand_categories(
            preferred=output.preferred_categories,
            excluded=output.excluded_categories,
        )

        return output


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
