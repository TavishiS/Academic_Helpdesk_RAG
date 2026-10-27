"""
Thin wrapper around ADK's Runner so the CLI and the evaluation script
can ask a question and get back the answer *plus* a trace of what happened
(which agent answered, which tools were called, what they returned).
"""
import uuid
from dataclasses import dataclass, field

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

import config
from helpdesk.agents import build_agent


@dataclass
class Answer:
    text: str = ""
    agent: str = ""                                    # agent that produced the final answer
    tool_calls: list = field(default_factory=list)     # [{"name", "args"}]
    tool_results: list = field(default_factory=list)   # [{"name", "response"}]
    llm_calls: int = 0                                 # token usage summed over all LLM calls
    prompt_tokens: int = 0
    output_tokens: int = 0

    @property
    def tools_used(self):
        return [c["name"] for c in self.tool_calls]

    @property
    def email_draft(self):
        """The last draft returned by the draft_email tool, if any."""
        for r in reversed(self.tool_results):
            if r["name"] == "draft_email" and isinstance(r["response"], dict) and "body" in r["response"]:
                return r["response"]
        return None

    @property
    def full_text(self):
        """Answer as shown to the student: the LLM's reply plus the email draft, printed verbatim
        from the tool result (so the email ID and wording can never be altered by the LLM)."""
        d = self.email_draft
        if not d:
            return self.text
        return (f"{self.text}\n\n----- EMAIL DRAFT ({d.get('status', 'not sent')}) -----\n"
                f"To: {d.get('to')}\nSubject: {d.get('subject')}\n\n{d.get('body')}\n" + "-" * 40)


class Helpdesk:
    def __init__(self, mode="multi", model_name=None):
        self.mode = mode
        self.model_name = model_name or config.LLM_MODEL
        self.session_service = InMemorySessionService()
        self.runner = Runner(agent=build_agent(mode, self.model_name), app_name=config.APP_NAME,
                             session_service=self.session_service)
        self.user_id = "student"
        self.session_id = None

    async def new_session(self):
        self.session_id = str(uuid.uuid4())
        await self.session_service.create_session(app_name=config.APP_NAME, user_id=self.user_id,
                                                  session_id=self.session_id)

    async def ask(self, question, fresh_session=False):
        if fresh_session or self.session_id is None:
            await self.new_session()

        ans = Answer()
        message = types.Content(role="user", parts=[types.Part(text=question)])
        async for event in self.runner.run_async(user_id=self.user_id, session_id=self.session_id,
                                                 new_message=message):
            usage = getattr(event, "usage_metadata", None)
            if usage and usage.prompt_token_count:
                ans.llm_calls += 1
                ans.prompt_tokens += usage.prompt_token_count
                ans.output_tokens += usage.candidates_token_count or 0
            for call in event.get_function_calls() or []:
                ans.tool_calls.append({"name": call.name, "args": dict(call.args or {})})
            for resp in event.get_function_responses() or []:
                ans.tool_results.append({"name": resp.name, "response": resp.response})
            if event.is_final_response() and event.content and event.content.parts:
                text = "".join(p.text or "" for p in event.content.parts).strip()
                if text:
                    ans.text, ans.agent = text, event.author
        if not ans.text:
            ans.text = "(no answer produced)"
        return ans
