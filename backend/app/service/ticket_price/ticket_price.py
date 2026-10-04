import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv
from ollama import AsyncClient, ResponseError

from app.core.settings import settings
from app.schemas.ticket_price import TicketInfo
from datetime import datetime

load_dotenv()

SERVICE_DIRECTORY = Path(__file__).resolve().parent
TICKET_PROMPT_FILEPATH = SERVICE_DIRECTORY / "ticket_prompt.txt"

MODEL = "gpt-oss:120b"

prompt = TICKET_PROMPT_FILEPATH.read_text(
    encoding="utf-8"
).strip()


client = AsyncClient(
    host="https://ollama.com",
    headers={
        "Authorization": f"Bearer {settings.ollama_api_key}"
    }
)
logger = logging.getLogger(__name__)


class TicketService:

    def __init__(self) -> None:
        self._cache: dict[str, TicketInfo] = {}
        self._web_search_unavailable = False

    async def get_ticket_info(
            self,
            place_name: str,
            visit_at: datetime | None = None
    ) -> TicketInfo:

        cache_key = place_name.casefold().strip()
        if cache_key in self._cache:
            return self._cache[cache_key]
        if self._web_search_unavailable:
            return TicketInfo()

        reference_datetime = (
                visit_at or datetime.now().astimezone()
        )

        query = (
            f'"{place_name}" Kraków '
            f'bilety cennik cena ticket price admission'
        )

        print(f"\nSEARCHING: {query}")

        try:
            search_result = await client.web_search(
                query=query,
                max_results=5,
            )
        except ResponseError as exc:
            if exc.status_code == 429:
                self._web_search_unavailable = True
                logger.warning(
                    "Ticket price lookup disabled for this run: Ollama web search "
                    "rate limit reached"
                )
                return TicketInfo()
            raise


        research_parts: list[str] = []

        for result in search_result.results:
            print(f"\nFOUND: {result.title}")
            print(result.url)

            print("\nSEARCH SNIPPET:")
            print(result.content[:2000])

            # Search snippet też może już zawierać cenę.
            research_parts.append(
                f"""
    SEARCH RESULT
    Title: {result.title}
    URL: {result.url}
    Snippet:
    {result.content}
    """
            )

            try:
                fetched = await client.web_fetch(
                    url=result.url
                )

                research_parts.append(
                    f"""
    FETCHED PAGE
    Title: {fetched.title}
    URL: {result.url}
    Content:
    {fetched.content[:12000]}
    """
                )

                print("\n" + "=" * 80)
                print(f"FETCHED URL: {result.url}")
                print(f"TITLE: {fetched.title}")
                print(f"CONTENT LENGTH: {len(fetched.content)}")
                print("-" * 80)
                print(fetched.content[:5000])
                print("=" * 80)

                research_parts.append(
                    f"""
                FETCHED PAGE
                Title: {fetched.title}
                URL: {result.url}
                Content:
                {fetched.content[:12000]}
                """
                )

            except Exception as e:
                print(f"FETCH FAILED: {e}")

        research = "\n\n".join(research_parts)

        messages = [
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": (
                    f"REFERENCE DATETIME: \n{reference_datetime.isoformat()}\n"
                    f"Attraction: {place_name}\n\n"
                    f"WEB RESEARCH:\n{research}"

                ),
            },
        ]
        research = "\n\n".join(research_parts)

        print("\n\n######## RESEARCH SENT TO LLM ########")
        print(research[:30000])
        print("######## END RESEARCH ########\n")

        response = await client.chat(
            model=MODEL,
            messages=messages,
            format=TicketInfo.model_json_schema(),
            think=False,
            options={
                "temperature": 0,
            },
            keep_alive="1m",
        )

        ticket_info = TicketInfo.model_validate_json(
            response.message.content
        )
        self._cache[cache_key] = ticket_info
        return ticket_info


async def main():
    service = TicketService()

    result = await service.get_ticket_info(
        "Zamek Królewski na Wawelu"
    )

    print("\nRESULT:")
    print(result)
    print(result.model_dump())


if __name__ == "__main__":
    asyncio.run(main())