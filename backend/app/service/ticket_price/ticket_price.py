import asyncio
from pathlib import Path

from dotenv import load_dotenv
from ollama import AsyncClient

from app.core.settings import settings
from app.schemas.ticket_price import TicketInfo
from datetime import datetime

load_dotenv()

SERVICE_DIRECTORY = Path(__file__).resolve().parent
TICKET_PROMPT_FILEPATH = SERVICE_DIRECTORY / "ticket_prompt.txt"

MODEL = "qwen3:30b"

prompt = TICKET_PROMPT_FILEPATH.read_text(
    encoding="utf-8"
).strip()


client = AsyncClient(
    headers={
        "Authorization": f"Bearer {settings.ollama_api_key}"
    }
)


class TicketService:


    async def get_ticket_info(
            self,
            place_name: str,
            visit_at: datetime | None = None
    ) -> TicketInfo:

        reference_datetime = (
                visit_at or datetime.now().astimezone()
        )

        query = (
            f'"{place_name}" Kraków '
            f'bilety cennik cena ticket price admission'
        )

        print(f"\nSEARCHING: {query}")

        search_result = await client.web_search(
            query=query,
            max_results=5,
        )


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

                fetched = await client.web_fetch(url=result.url)

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

        return TicketInfo.model_validate_json(
            response.message.content
        )


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