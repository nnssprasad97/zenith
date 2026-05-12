from groq import AsyncGroq
import os


class GroqProvider:
    name = "groq"

    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or os.getenv("GROQ_API_KEY")
        self.model = config.get("model", "llama-3.3-70b-versatile")
        self.client = AsyncGroq(api_key=self.api_key)

    async def chat(self, messages: list, tools=None) -> str:
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=1024
        )
        return response.choices[0].message.content

