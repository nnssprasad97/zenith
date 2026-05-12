from openai import AsyncOpenAI
import os


class OpenRouterProvider:
    name = "openrouter"

    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or os.getenv("OPENROUTER_API_KEY")
        self.model = config.get("model", "meta-llama/llama-3.3-70b-instruct")
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1", api_key=self.api_key
        )

    async def chat(self, messages: list, tools=None) -> str:
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages
        )
        return response.choices[0].message.content

