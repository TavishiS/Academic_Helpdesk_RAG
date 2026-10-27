"""
Structured lookups over the CSV files in the knowledge base.

Why not only RAG? Questions like "what is the slot of CSL7570" or "how many
400-level HSS electives" need exact matching / counting. Embedding search is
bad at exact codes and cannot count, so the CSVs are also loaded as tables here.

Column names differ between files (e.g. "Course Code" vs "code"), so each
logical field has a list of aliases. A CSV is treated as:
  - a course table  if it has a course-code column   (timetable, course list, ...)
  - a faculty table if it has an email column + a name column
"""
import re
from difflib import SequenceMatcher
from functools import lru_cache

import pandas as pd

import config

ALIASES = {
    "course_code": ["course code", "course_code", "code", "course no", "course number", "course id", "subject code"],
    "course_name": ["course name", "course_name", "course title", "title", "course", "subject", "subject name"],
    "instructor": ["instructor", "instructor name", "faculty", "faculty name", "course instructor", "taught by",
                   "professor", "coordinator", "course coordinator"],
    "slot": ["slot", "time slot", "timeslot", "lecture slot"],
    "department": ["department", "dept", "discipline", "offered by", "offering department"],
    "course_type": ["type", "course type", "category", "course category", "elective/core", "core/elective"],
    "credits": ["credits", "credit", "l-t-p", "ltp", "credit structure"],
    "email": ["email", "email id", "e-mail", "mail", "email address"],
    "person_name": ["name", "faculty name", "instructor", "faculty", "full name"],
}


def _norm(s):
    return re.sub(r"[^a-z0-9/]+", " ", str(s).lower()).strip()


def _find_col(df, field):
    cols = {_norm(c): c for c in df.columns}
    for alias in ALIASES[field]:
        if alias in cols:
            return cols[alias]
    return None


def _norm_code(code):
    return re.sub(r"[^A-Z0-9]", "", str(code).upper())


def _clean_person(name):
    name = re.sub(r"\b(dr|prof|professor|mr|mrs|ms)\b\.?", " ", str(name).lower())
    return " ".join(re.sub(r"[^a-z ]", " ", name).split())


@lru_cache(maxsize=1)
def load_tables():
    """Return (courses_df, faculty_df). Columns renamed to the logical field names."""
    course_frames, faculty_frames = [], []
    for path in sorted(config.KB_DIR.rglob("*.csv")):
        try:
            df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding_errors="replace")
        except Exception as e:
            print(f"[csv_store] could not read {path.name}: {e}")
            continue
        df.columns = [str(c).strip() for c in df.columns]

        if _find_col(df, "course_code"):
            rename = {}
            for field in ["course_code", "course_name", "instructor", "slot", "department",
                          "course_type", "credits", "email"]:
                col = _find_col(df, field)
                if col and col not in rename:
                    rename[col] = field
            t = df.rename(columns=rename)
            t["source"] = path.name
            course_frames.append(t)
        elif _find_col(df, "email") and _find_col(df, "person_name"):
            t = df.rename(columns={_find_col(df, "email"): "email", _find_col(df, "person_name"): "name"})
            t["source"] = path.name
            faculty_frames.append(t)

    courses = pd.concat(course_frames, ignore_index=True).fillna("") if course_frames else pd.DataFrame()
    faculty = pd.concat(faculty_frames, ignore_index=True).fillna("") if faculty_frames else pd.DataFrame()
    return courses, faculty


def _row_to_dict(row):
    return {k: v for k, v in row.items() if str(v).strip()}


def find_course(query):
    """Match by course code first (exact, ignoring spaces), then by course name (substring / fuzzy)."""
    courses, _ = load_tables()
    if courses.empty:
        return []

    code = _norm_code(query)
    by_code = courses[courses["course_code"].map(_norm_code) == code]
    if not by_code.empty:
        return [_row_to_dict(r) for _, r in by_code.iterrows()]

    if "course_name" not in courses:
        return []
    q = _norm(query)
    names = courses["course_name"].map(_norm)
    by_name = courses[names.str.contains(re.escape(q), regex=True)] if q else courses.iloc[0:0]
    if not by_name.empty:
        return [_row_to_dict(r) for _, r in by_name.iterrows()]

    # fuzzy fallback for typos like "autonomus systems"
    scores = names.map(lambda n: SequenceMatcher(None, q, n).ratio())
    best = scores[scores >= 0.75]
    return [_row_to_dict(courses.loc[i]) for i in best.sort_values(ascending=False).index[:3]]


def find_email(person):
    """Look up a faculty email by name. Returns list of {name, email, source}."""
    _, faculty = load_tables()
    if faculty.empty or not str(person).strip():
        return []
    target = _clean_person(person)
    tokens = [t for t in target.split() if len(t) > 1]
    out = []
    for _, r in faculty.iterrows():
        cand = _clean_person(r["name"])
        if cand == target or (tokens and all(t in cand.split() for t in tokens)):
            out.append({"name": r["name"], "email": r["email"], "source": r["source"]})
    return out


# words the LLM likes to add ("Humanities department", "elective courses") that never appear in the CSV values
_FILLER = {"department", "dept", "of", "and", "the", "school", "centre", "center", "course", "courses"}


def _words_match(query, value):
    """True if every meaningful word of `query` occurs in `value`; plurals also match
    ("electives" matches "Elective"). An empty query matches everything."""
    val = _norm(value)
    words = [w for w in _norm(query).split() if w not in _FILLER]
    return all(w in val or (w.endswith("s") and w[:-1] in val) for w in words)


def _level_of(code):
    """CSL7570 -> '7', HSL4010 -> '4'. The first digit of the numeric part gives the level."""
    m = re.search(r"\d", str(code))
    return m.group(0) if m else ""


def count_courses(department, level, course_type):
    """Filter the course table; empty string means 'no filter' for that field."""
    courses, _ = load_tables()
    if courses.empty:
        return []
    df = courses.drop_duplicates(subset=["course_code"])

    if department.strip():
        # a department may be stored as a column or only be visible from the code prefix (HSL..., CSL...)
        mask = df["course_code"].str.upper().str.startswith(department.strip().upper()[:2])
        if "department" in df:
            mask = mask | df["department"].map(lambda d: _words_match(department, d))
        df = df[mask]
    if level.strip():
        digit = re.search(r"\d", level)
        if digit:
            df = df[df["course_code"].map(_level_of) == digit.group(0)]
    if course_type.strip() and "course_type" in df:
        df = df[df["course_type"].map(lambda t: _words_match(course_type, t))]

    return [_row_to_dict(r) for _, r in df.iterrows()]
