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


# fields of a course shown to the LLM (in this order); empty ones are left out to keep prompts short
_COURSE_FIELDS = ["course_code", "course_name", "department", "instructor", "slot", "timings", "lab_slot",
                  "credits", "ltp", "course_type", "program", "year", "section", "remarks", "source"]


def _course_view(row):
    row = dict(row)
    row["timings"] = csv_store.timings_for(f"{row.get('slot', '')} {row.get('lab_slot', '')}")
    return {k: row[k] for k in _COURSE_FIELDS if row.get(k)}


def _course_label(row):
    return f"{row.get('course_code', '')} {row.get('course_name', '')}".strip()


def lookup_course(course: str) -> dict:
    """Get the slot, class timings, instructor, credits etc. of a course from the timetable.
    Also gives the timings of a slot: use e.g. "slot D".

    Args:
        course: course code (e.g. "CSL7650"), course name, abbreviation (e.g. "DSA"), or "slot D".
    """
    if csv_store.is_department(course):
        return {"error": f"'{course}' is a department, not a course. "
                         f"Use list_courses to list the courses of a department."}
    slot = csv_store.slot_query(course)
    if slot:
        return {"slot": slot, "timings": csv_store.timings_for(slot), "source": csv_store.slot_grid_files()}
    matches = csv_store.find_course(course)
    if not matches:
        return {"matches": [], "error": f"No course matching '{course}' in the timetable files."}
    return {"matches": [_course_view(m) for m in matches[:5]]}


def list_courses(department: str, level: str, course_type: str) -> dict:
    """List or count the courses offered this semester, with instructor and slot.
    Use "" for a filter that is not needed. The list is shown to the student automatically.

    Args:
        department: the offering department, e.g. "CSE", "Electrical", "Mechanical", "Civil",
            "Humanities", or "". NEVER put a department name here in course_type.
        level: first digit of course code, e.g. "1", "4", "6", "7", or "".
            "400 level" means level="4"; "100 level" means level="1".
        course_type: academic category only: "elective", "core", or "". Never a department name.
    """
    if department.strip() and not csv_store.has_department(department):
        return {"error": f"There is no timetable data for the department '{department}'.",
                "available_departments": csv_store.departments()}
    rows = csv_store.count_courses(department, level, course_type)
    # collect all source files that were actually searched so the LLM can cite them
    all_sources = sorted({r["source"] for r in csv_store.count_courses(department, "", "")}) \
        if department.strip() else sorted({r["source"] for r in csv_store.count_courses("", "", "")})
    # one short line per course: the LLM reads these on every call, so no timings/credits here
    lines = [" | ".join(x for x in [_course_label(r), r.get("instructor", ""),
                                    f"slot {r['slot']}" if r.get("slot") else ""] if x) for r in rows]
    result = {
        # a ready-made sentence: small models misread a bare {"count": 2} surprisingly often
        "summary": f"{len(rows)} course(s) match.",
        "count": len(rows),
        "rows": lines,
        "source": sorted({r["source"] for r in rows}) if rows else all_sources,
    }
    if not rows:
        result["note"] = ("No courses match the given filters. "
                          "Check that department, level and course_type are correct. "
                          "course_type must be 'elective', 'core' or '' — never a department name.")
    return result


def lookup_instructor_email(course_code: str) -> dict:
    """Get the instructor's name and email ID for a course.

    Args:
        course_code: course code (e.g. "CSL7650"), course name or abbreviation.
    """
    matches = csv_store.find_course(course_code)
    if not matches:
        return {"error": f"Course '{course_code}' not found in the timetable files."}
    # prefer a row that names a person (some rows say "TBD" or "ELECTRONICS Dept.")
    course = next((m for m in matches if csv_store.split_people(m.get("instructor", ""))), matches[0])
    people = csv_store.split_people(course.get("instructor", ""))
    result = {"course": _course_label(course), "instructor": course.get("instructor") or "unknown"}
    others = sorted({f"{_course_label(m)} ({m.get('instructor', '?')})" for m in matches
                     if _course_label(m) != result["course"]})
    if others:
        result["other_matching_courses"] = others[:5]

    sources, found, missing = {course["source"]}, [], []
    if course.get("email"):                       # some timetables already contain the email
        found = [{"name": course.get("instructor", ""), "email": course["email"]}]
    else:
        for person in people:                     # a course can have several instructors
            hit = csv_store.find_email(person)
            if hit:
                found.append(hit[0])
                sources.add(hit[0]["source"])
            else:
                missing.append(person)
    result["source"] = sorted(sources)

    if not found:
        result["error"] = ("The timetable does not name the instructor." if not people
                           else "Email ID of the instructor not found in the faculty directory.")
        return result
    result["instructor"] = ", ".join(h["name"] for h in found)
    result["email"] = ", ".join(h["email"] for h in found)
    if missing:
        result["note"] = f"No email ID found for: {', '.join(missing)}"
    return result


def draft_email(course_code: str, request_type: str, reason: str, dates: str) -> dict:
    """Draft (not send) an email to the instructor of a course. The email ID is filled in automatically.

    Args:
        course_code: course code or name, e.g. "CSL7650".
        request_type: "leave" or "makeup" (makeup exam).
        reason: e.g. "fever", or "".
        dates: e.g. "2 days", "24-25 Oct", or "".
    """
    info = lookup_instructor_email(course_code)
    to = info.get("email", "[instructor email not found - please add]")
    names = csv_store.split_people(info.get("instructor", "")) if info.get("email") else []
    greeting = " and ".join(f"Prof. {n}" for n in names) or "Sir/Madam"
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

    body = (f"Dear {greeting},\n\n{ask}\n\nThank you for your consideration.\n\n"
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
