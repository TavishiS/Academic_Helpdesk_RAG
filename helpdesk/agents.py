"""
Agent definitions (Google ADK + Ollama through LiteLLM).

Two architectures, so they can be compared in the evaluation:
  single : one agent that has every tool
  multi  : helpdesk orchestrator -> policy_agent / schedule_agent / email_agent
           (ADK's LLM-driven delegation: the orchestrator calls transfer_to_agent)

Instructions are short on purpose: they are re-sent with every LLM call and
reading the prompt is the slowest part of answering on a CPU.
"""
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

import config
from helpdesk.tools import (draft_email, list_courses, log_unanswered_question, lookup_course,
                            lookup_instructor_email, search_documents)

# Rules shared by every agent. Small models follow short, numbered, imperative rules best.
GROUNDING_RULES = f"""
RULES:
1. Use ONLY facts from tool results. Never guess numbers, slots, names or email IDs.
2. Call a tool before answering.
3. First write the answer as a full sentence with the facts (e.g. the number, slot or rule). Then, on a new line,
   "Source: <file name>", copying the "cite_as" (or "source") value of the tool result exactly,
   e.g. "Source: timetable.csv". It is a FILE name, never a tool name; never add pages yourself.
4. Refuse ONLY if the question is not academic, or the tool result is empty or has an "error". A count or a
   course row IS an answer. To refuse: call log_unanswered_question and reply exactly:
   "{config.REFUSAL_TEXT}" (nothing else, no source).
5. Be brief.
"""

# The draft itself is printed by the program straight from the tool result (session.Answer.full_text),
# so the LLM does not have to retype ~100 tokens of email body at ~6 tokens/s.
EMAIL_RULE = 'To write an email call draft_email (request_type "leave" or "makeup"). The draft is shown to ' \
             'the student automatically: just reply in one line that the draft is ready to review and was NOT sent ' \
             '(no Source line).'


def make_model(model_name=None):
    model_name = model_name or config.LLM_MODEL
    # "ollama_chat/" (not "ollama/") is the provider prefix that supports tool calling properly.
    # max_tokens caps the answer length so a model that starts repeating itself cannot run for minutes.
    return LiteLlm(model=f"ollama_chat/{model_name}", temperature=config.TEMPERATURE, num_ctx=config.NUM_CTX,
                   max_tokens=config.MAX_OUTPUT_TOKENS)


# ------------------------------------------------------------------ single agent

def build_single_agent(model_name=None):
    return Agent(
        name="academic_helpdesk",
        model=make_model(model_name),
        description="Academic helpdesk.",
        instruction=f"""You are the institute's Academic Helpdesk. Pick the tool:
- rules, attendance, grading, credits, degree requirements, curriculum, office orders: search_documents
- slot, class timings, instructor or credits of a course, or timings of a slot ("slot D"): lookup_course
- list or count courses: list_courses. Put the department name in `department` (e.g. "Humanities",
  "CSE", "Electrical"), the level digit in `level` (e.g. "4" for 400-level), and only "elective"/
  "core"/"" in `course_type` — never a department name in course_type. Use "" for unused filters.
  The list is shown to the student automatically, so just reply with one sentence giving the number.
- instructor email ID: lookup_instructor_email
- {EMAIL_RULE}
{GROUNDING_RULES}""",
        tools=[search_documents, lookup_course, list_courses, lookup_instructor_email,
               draft_email, log_unanswered_question],
    )


# ------------------------------------------------------------------ multi agent

def build_multi_agent(model_name=None):
    model = make_model(model_name)

    # ADK shows each sub-agent's `description` to the orchestrator for routing
    policy_agent = Agent(
        name="policy_agent",
        model=model,
        description="Academic rules and regulations: attendance, grading, exams, credit and degree requirements, "
                    "curriculum. Not for timetable questions or listing/counting courses.",
        instruction=f"""You answer questions on academic rules, programs and curriculum.
Call search_documents (search again with other words if the results don't answer it).
{GROUNDING_RULES}""",
        tools=[search_documents, log_unanswered_question],
        disallow_transfer_to_peers=True,
    )

    schedule_agent = Agent(
        name="schedule_agent",
        model=model,
        description="Timetable and courses offered this semester: course slots and class timings, instructor of a course, "
                    "exam dates, listing the courses of a department, and every 'how many courses/electives' question.",
        instruction=f"""You answer timetable questions.
- slot, class timings, instructor or credits of a course, or timings of a slot ("slot D"): lookup_course
- list or count courses: list_courses. Put the department name in `department` (e.g. "Humanities",
  "CSE", "Electrical"), the level digit in `level` (e.g. "4" for 400-level), and only "elective"/
  "core"/"" in `course_type` — never a department name in course_type. Use "" for unused filters.
  The list is shown to the student automatically, so reply with one sentence giving the number.
- exam dates, academic calendar: search_documents
{GROUNDING_RULES}""",
        tools=[lookup_course, list_courses, search_documents, log_unanswered_question],
        disallow_transfer_to_peers=True,
    )

    email_agent = Agent(
        name="email_agent",
        model=model,
        description="Instructor email IDs; leave and makeup-exam email drafts.",
        instruction=f"""You help students contact instructors.
- only the email ID: lookup_instructor_email
- {EMAIL_RULE}
{GROUNDING_RULES}""",
        tools=[lookup_instructor_email, draft_email, log_unanswered_question],
        disallow_transfer_to_peers=True,
    )

    orchestrator = Agent(
        name="helpdesk_orchestrator",
        model=model,
        description="Front desk; routes questions to specialist agents.",
        instruction=f"""You are the Academic Helpdesk front desk. Do NOT answer yourself:
transfer every academic question to policy_agent, schedule_agent or email_agent.
If the question is not academic (food, hostel, travel, sports, general knowledge), do not transfer:
call log_unanswered_question and reply exactly: "{config.REFUSAL_TEXT}"
""",
        tools=[log_unanswered_question],
        sub_agents=[policy_agent, schedule_agent, email_agent],
    )
    return orchestrator


def build_agent(mode="multi", model_name=None):
    if mode == "single":
        return build_single_agent(model_name)
    if mode == "multi":
        return build_multi_agent(model_name)
    raise ValueError(f"unknown mode {mode!r} (use 'single' or 'multi')")
