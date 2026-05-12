import google.generativeai as genai
import os


class GeminiProvider:
    name = "gemini"

    def __init__(self, config: dict):
        self.api_key = config.get("api_key") or os.getenv("GOOGLE_API_KEY")
        self.model_name = config.get("model", "gemini-2.5-flash")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

    async def chat(self, messages: list, tools=None) -> str:
        history = []
        for msg in messages[:-1]:
            history.append(
                {
                    "role": "user" if msg["role"] == "user" else "model",
                    "parts": [msg["content"]],
                }
            )
        last_message = messages[-1]["content"]

        chat = self.model.start_chat(history=history)
        response = chat.send_message(last_message)
        return response.text

