"""
Tools exposed to the agents.

ADK turns each Python function into a tool: the function name, type hints and
docstring become the schema the LLM sees, so docstrings are written for the LLM.
They are also sent with EVERY LLM call, so they are kept short (on a CPU the
model reads only ~20 tokens/s). Small 8B models are much better at filling plain
string arguments, so every parameter is a required `str` (no defaults, no nested
objects). Every result carries a `source` so the agent can cite it.
"""
import csv
from datetime import datetime

import config
from helpdesk import csv_store, retriever


def _shorten(text, limit):
    """Cut a passage to `limit` chars, preferably at the end of a sentence."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = cut.rfind(". ")
    return cut[:end + 1] if end > limit * 0.6 else cut + "..."


def search_documents(query: str) -> dict:
    """Search the academic documents (rules, regulations, curriculum, office orders, calendar).

    Args:
        query: short search query, e.g. "attendance requirement major exam".
    """
    hits = retriever.retrieve(query)
    relevant = [h for h in hits if h["similarity"] >= config.MIN_SIMILARITY]
    if not relevant:
        return {"results": [],
                "note": "Nothing relevant found. Do not guess: call log_unanswered_question and refuse."}
    return {"results": [{
        "text": _shorten(h["text"], config.MAX_PASSAGE_CHARS),
        "source": h["source"],
        "cite_as": f"{h['source']}, p.{h['page']}" if h.get("page") else h["source"],
        "similarity": h["similarity"],
    } for h in relevant]}


def lookup_course(course: str) -> dict:
    """Get the slot, instructor, credits etc. of a course from the timetable.

    Args:
        course: course code (e.g. "CSL7570") or course name.
    """
    matches = csv_store.find_course(course)
    if not matches:
        return {"matches": [], "error": f"No course matching '{course}' in the timetable files."}
    return {"matches": matches[:5]}


def count_courses(department: str, level: str, course_type: str) -> dict:
    """Count the courses offered this semester. Use "" for a filter that is not needed.

    Args:
        department: e.g. "Humanities", "CSE", or "".
        level: e.g. "400", or "".
        course_type: e.g. "elective", "core", or "".
    """
    rows = csv_store.count_courses(department, level, course_type)
    return {
        "count": len(rows),
        "courses": [f"{r.get('course_code')} {r.get('course_name', '')}".strip() for r in rows],
        "source": sorted({r["source"] for r in rows}),
    }


def lookup_instructor_email(course_code: str) -> dict:
    """Get the instructor's name and email ID for a course.

    Args:
        course_code: course code (e.g. "CSL7570") or course name.
    """
    matches = csv_store.find_course(course_code)
    if not matches:
        return {"error": f"Course '{course_code}' not found in the timetable files."}
    course = matches[0]
    instructor = course.get("instructor", "")
    sources = [course["source"]]

    email = course.get("email", "")  # some timetables already contain the email
    if not email and instructor:
        # a course can have several instructors: "Dr. A, Dr. B" -> take the first one found
        for name in [n for n in instructor.replace(" and ", ",").split(",") if n.strip()]:
            found = csv_store.find_email(name)
            if found:
                email = found[0]["email"]
                sources.append(found[0]["source"])
                break

    if not email:
        return {"course": course.get("course_code"), "instructor": instructor or "unknown",
                "error": "Email ID of the instructor not found in the faculty directory.", "source": sources}
    return {"course": f"{course.get('course_code')} {course.get('course_name', '')}".strip(),
            "instructor": instructor, "email": email, "source": sources}


def draft_email(course_code: str, request_type: str, reason: str, dates: str) -> dict:
    """Draft (not send) an email to the instructor of a course. The email ID is filled in automatically.

    Args:
        course_code: course code or name, e.g. "CSL7570".
        request_type: "leave" or "makeup" (makeup exam).
        reason: e.g. "fever", or "".
        dates: e.g. "2 days", "24-25 Oct", or "".
    """
    info = lookup_instructor_email(course_code)
    to = info.get("email", "[instructor email not found - please add]")
    instructor = info.get("instructor") or "Sir/Madam"
    course = info.get("course") or course_code
    reason = reason.strip() or "[reason]"
    dates = dates.strip() or "[dates]"

    if "make" in request_type.lower() or "exam" in request_type.lower():
        subject = f"Request for makeup examination - {course}"
        ask = (f"I could not appear for the examination ({dates}) due to {reason}. "
               f"I kindly request you to permit me to take a makeup examination. "
               f"I will submit the supporting documents (e.g. medical certificate) as required by the institute rules.")
    else:
        subject = f"Leave application for {dates} - {course}"
        ask = (f"I am writing to inform you that I will not be able to attend the classes of {course} "
               f"for {dates} due to {reason}. I kindly request you to grant me leave for this period. "
               f"I will make up for the missed content and can share supporting documents if needed.")

    body = (f"Dear {instructor},\n\n{ask}\n\nThank you for your consideration.\n\n"
            f"Regards,\n[Your Name]\n[Roll Number]\n[Program, Year]")
    return {"to": to, "subject": subject, "body": body, "status": "DRAFT - not sent",
            "source": info.get("source", [])}


def log_unanswered_question(question: str, reason: str) -> dict:
    """Log a question you cannot answer so a human can answer it later. Call this whenever you refuse.

    Args:
        question: the user's question, as asked.
        reason: e.g. "out of scope" or "not found in documents".
    """
    config.LOG_DIR.mkdir(exist_ok=True)
    new_file = not config.UNANSWERED_LOG.exists()
    with open(config.UNANSWERED_LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "question", "reason"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), question, reason])
    return {"status": "logged for human review"}
