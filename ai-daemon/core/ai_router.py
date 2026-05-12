"""
JARVIS AI — AI Router (Agent-Aware)
Routes user commands through the autonomous agent pipeline:
  Command → Context Resolution → Agent Decomposition → Task Execution → Response

Supports:
  - Multi-task compound commands
  - Follow-up context resolution ("send again", "open that app")
  - Single-task fast path for simple commands
  - Memory-based conversation continuity
"""

import logging

logger = logging.getLogger("jarvis.router")


class AIRouter:
    """
    Central routing engine with agent intelligence.
    Orchestrates: command → resolve context → decompose → execute → remember
    """

    def __init__(self):
        from core.intent_classifier import get_classifier
        from core.executor import get_executor
        from core.memory import get_memory
        from core.agent import decompose_command
        from core.task_runner import get_task_runner

        self.classifier = get_classifier()
        self.executor = get_executor()
        self.memory = get_memory()
        self.decompose = decompose_command
        self.task_runner = get_task_runner()

        self._llm = None

    @property
    def llm(self):
        """Lazy-load LLM client."""
        if self._llm is None:
            try:
                from ai.llm_client import get_llm_client
                self._llm = get_llm_client()
            except Exception:
                pass
        return self._llm

    def process(self, command: str) -> str:
        """
        Process a user command through the full autonomous pipeline.

        Returns:
            Response string (already human-readable).
            Returns "__EXIT__" to signal shutdown.
        """
        if not command or not command.strip():
            return ""

        logger.info(f"Processing: '{command}'")

        # Step 0: Resolve context from memory (handle follow-ups)
        resolved_command = self._resolve_context(command)
        if resolved_command != command:
            logger.info(f"Context resolved: '{command}' → '{resolved_command}'")

        # Step 1: Check for incomplete commands that need clarification
        clarification = self._check_clarification(resolved_command)
        if clarification:
            return clarification

        # Step 1.5: Intercept general questions for GUI/SerpAPI handling
        cmd_lower = resolved_command.lower()
        question_words = ["who", "what", "where", "when", "why", "how", "explain", "search", "find", "tell", "can you", "show"]
        is_question = any(cmd_lower.startswith(w) for w in question_words) or "?" in cmd_lower or "explain" in cmd_lower or "search" in cmd_lower
        
        # Exclude specific intents that shouldn't be intercepted
        excluded_keywords = ["time", "date", "weather", "open", "play", "call", "message", "email"]
        if is_question and not any(w in cmd_lower for w in excluded_keywords):
            from core.speech import speak, listen
            speak("This is a potentially dangerous action: GUI and keyboard automation. Are you sure?")
            response = listen()
            
            result_str = ""
            resp_lower = response.lower() if response else ""
            is_positive = any(w in resp_lower for w in ["yes", "yeah", "proceed", "go ahead", "do it", "confirm"]) or ("sure" in resp_lower and "not sure" not in resp_lower)
            
            if response and is_positive:
                try:
                    import pyautogui
                    import time
                    import webbrowser
                    speak("Proceeding ahead.")
                    webbrowser.open("https://google.com")
                    time.sleep(2)
                    pyautogui.write(resolved_command)
                    time.sleep(0.5)
                    pyautogui.press('enter')
                    result_str = "Search automated using GUI."
                except Exception as e:
                    result_str = f"Automation failed: {e}"
            else:
                try:
                    import requests
                    api_key = "3e5a9b6212fc7350057c1b6a699868ba0f9594bf6b9f571459c3fc0df46c5c2a"
                    url = "https://serpapi.com/search"
                    params = {"q": resolved_command, "api_key": api_key}
                    resp = requests.get(url, params=params, timeout=10)
                    if resp.status_code == 200:
                        data = resp.json()
                        answer = ""
                        if "answer_box" in data and "answer" in data["answer_box"]:
                            answer = data["answer_box"]["answer"]
                        elif "answer_box" in data and "snippet" in data["answer_box"]:
                            answer = data["answer_box"]["snippet"]
                        elif "organic_results" in data and len(data["organic_results"]) > 0:
                            answer = data["organic_results"][0].get("snippet", "I couldn't find a direct answer.")
                        
                        result_str = f"Here is the answer: {answer}" if answer else "I searched the web but couldn't find a clear answer."
                    else:
                        result_str = "Failed to fetch from SerpAPI."
                except Exception as e:
                    result_str = f"SerpAPI request failed: {e}"
            
            # Remember the interaction
            self.memory.remember_command(
                command=command,
                intent="question",
                result=result_str,
            )
            return result_str

        # Step 2: Try multi-task decomposition (compound commands)
        tasks = self.decompose(resolved_command, llm=self.llm)

        if tasks and len(tasks) > 1:
            # Multi-task: run through task runner
            logger.info(f"Multi-task pipeline: {len(tasks)} tasks")
            result = self.task_runner.run(tasks)

            # Remember the compound command
            self.memory.remember_command(
                command=command,
                intent="multi_task",
                result=result,
            )
            # Track context for follow-ups
            self._update_context(tasks)

            return result

        # Step 3: Single-task — use normal classify → execute pipeline
        intent_data = self.classifier.classify(resolved_command)
        intent = intent_data.get("intent", "unknown")

        logger.info(
            f"Classified: intent={intent}, "
            f"confidence={intent_data.get('confidence', 0)}"
        )

        # Step 4: Execute
        result = self.executor.execute(intent_data)

        # Step 5: Remember
        self.memory.remember_command(
            command=command,
            intent=intent,
            result=result if result != "__EXIT__" else "Goodbye",
        )

        # Track context for follow-ups
        self._update_single_context(intent, intent_data.get("entities", {}))

        return result

    def _resolve_context(self, command: str) -> str:
        """
        Resolve follow-up commands using conversation context.

        Handles:
          - "send again" → re-sends last message
          - "reply him" / "reply her" → sends to last contact
          - "open that app" → opens the last opened app
          - "do it again" → repeats last command
        """
        cmd_lower = command.lower().strip()

        # "send again" / "send it again"
        if any(p in cmd_lower for p in ["send again", "send it again", "resend"]):
            last_contact = self.memory.get_last_context("contact")
            last_message = self.memory.get_last_context("message")
            if last_contact and last_message:
                return f"send whatsapp message to {last_contact} saying {last_message}"
            elif last_contact:
                return f"send whatsapp message to {last_contact}"

        # "reply him" / "reply her" / "reply them"
        if any(p in cmd_lower for p in ["reply him", "reply her", "reply them", "reply to"]):
            last_contact = self.memory.get_last_context("contact")
            if last_contact:
                # Extract the message part
                msg = cmd_lower
                for prefix in ["reply him ", "reply her ", "reply them ", "reply to him ", "reply to her "]:
                    if msg.startswith(prefix):
                        msg = msg[len(prefix):]
                        break
                if msg and msg != cmd_lower:
                    return f"send whatsapp message to {last_contact} saying {msg}"
                return f"message {last_contact}"

        # "open that app" / "open it again"
        if any(p in cmd_lower for p in ["open that app", "open it again", "open that"]):
            last_app = self.memory.get_last_context("app")
            if last_app:
                return f"open {last_app}"

        # "do it again" / "repeat" / "again"
        if cmd_lower in ("do it again", "repeat", "again", "do that again"):
            last_cmd = self.memory.get_last_context("last_command")
            if last_cmd:
                return last_cmd

        return command

    def _check_clarification(self, command: str) -> str | None:
        """
        Detect incomplete commands that need clarification.
        Returns a clarification question, or None if command is complete.
        """
        cmd_lower = command.lower().strip()

        # "send message" without recipient
        if cmd_lower in ("send message", "send a message", "send msg", "message"):
            return "__CLARIFY__:To whom should I send the message?"

        # "send email" without recipient
        if cmd_lower in ("send email", "send an email", "send mail"):
            return "__CLARIFY__:Who should I send the email to?"

        # "open" alone
        if cmd_lower == "open":
            return "__CLARIFY__:What would you like me to open?"

        # "play" alone
        if cmd_lower == "play":
            return "__CLARIFY__:What would you like me to play?"

        # "search" alone
        if cmd_lower in ("search", "search for", "look up"):
            return "__CLARIFY__:What should I search for?"

        # "call" without contact
        if cmd_lower in ("call", "make a call"):
            return "__CLARIFY__:Who should I call?"

        # "set timer" without duration
        if cmd_lower in ("set timer", "set a timer", "timer"):
            return "__CLARIFY__:How long should I set the timer for?"

        # "remind me" without details
        if cmd_lower in ("remind me", "set reminder", "reminder"):
            return "__CLARIFY__:What should I remind you about?"

        return None

    def _update_context(self, tasks):
        """Update conversation context after multi-task execution."""
        for task in tasks:
            if task.action == "open_app":
                self.memory.set_context("app", task.target)
            elif task.action == "open_website":
                self.memory.set_context("app", task.target)
            elif task.action == "send_message":
                contact = task.params.get("contact", "")
                message = task.params.get("message", "")
                if contact:
                    self.memory.set_context("contact", contact)
                if message:
                    self.memory.set_context("message", message)

    def _update_single_context(self, intent: str, entities: dict):
        """Update conversation context after single-task execution."""
        if intent in ("open_app", "open_website"):
            app = entities.get("app", entities.get("url", ""))
            if app:
                self.memory.set_context("app", app)
        elif intent in ("send_whatsapp", "send_email"):
            contact = entities.get("recipient", "")
            message = entities.get("body", "")
            if contact:
                self.memory.set_context("contact", contact)
            if message:
                self.memory.set_context("message", message)
        elif intent == "play_media":
            query = entities.get("query", "")
            if query:
                self.memory.set_context("media", query)


# ============================================
# SINGLETON
# ============================================
_router = None


def get_router() -> AIRouter:
    """Get or create global AI router."""
    global _router
    if _router is None:
        _router = AIRouter()
    return _router
