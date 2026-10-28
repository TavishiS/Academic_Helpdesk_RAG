"""
Structured lookups over the CSV files in the knowledge base.

Why not only RAG? Questions like "what is the slot of CSL7650" or "how many
400-level electives" need exact matching / counting. Embedding search is bad
at exact codes and cannot count, so the CSVs are also loaded as tables here.

Real timetable exports are messy, so tables are read row by row instead of
with a plain pd.read_csv():
  - the header row is detected anywhere in the file (and may repeat with a
    different column order, as in mechanical.csv)
  - header names differ between files ("COURSE CODE (CIL)", "Course name",
    "Course Coordinator", "Instructor(s)"), so each logical field has aliases
  - blank rows are skipped, single-cell rows are section titles
    ("PG Semester-2 (AME)"), a row without a course name continues the
    course above it
  - a course code in a column without a header is still recognised
  - files without a Department column get it from config.DEPARTMENT_BY_FILE

Three kinds of CSV are recognised:
  - course table : has a course code / course name header (timetables)
  - faculty table: has an email column + a name column (faculty_contacts.csv)
  - slot grid    : a weekly grid with Mon, Tue, ... columns (slot_system.csv)
"""
import csv
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import pandas as pd

import config

# header aliases, compared after _norm_header() (lowercase, no punctuation, no "(...)")
COURSE_ALIASES = {
    "course_code": ["course code", "code", "course no", "course number", "course id", "subject code"],
    "course_name": ["course name", "course title", "title", "course", "subject", "subject name"],
    "instructor": ["instructor", "instructors", "instructor name", "faculty", "faculty name",
                   "course instructor", "taught by", "professor", "coordinator", "course coordinator"],
    "co_instructor": ["co instructor", "co instructors"],
    "slot": ["slot", "slots", "time slot", "timeslot", "lecture slot", "theory slot"],
    "lab_slot": ["lab slot", "lab slots"],
    "department": ["department", "dept", "discipline", "offered by", "offering department"],
    "course_type": ["type", "course type", "category", "course category", "elective/core", "core/elective"],
    "credits": ["credits", "credit"],
    "ltp": ["l t p", "ltp", "l t p structure", "credit structure"],
    "program": ["program", "programme", "batch"],
    "year": ["year"],
    "email": ["email", "email id", "e mail", "mail", "email address"],
}
FACULTY_ALIASES = {
    "email": COURSE_ALIASES["email"],
    "name": ["name", "faculty name", "instructor", "faculty", "full name"],
}

# course-type codes used in the timetables, expanded so that "elective" / "core" can be matched
TYPE_NAMES = {
    "PC": "Programme Core", "PE": "Programme Elective", "C": "Core", "E": "Elective",
    "MC": "M.Tech Core", "ME": "M.Tech Elective", "DC": "PhD Core",
    "T": "Thesis", "MT": "Thesis", "DT": "Thesis",
}

CODE_RE = re.compile(r"^[A-Z]{2,4}\d[0-9X]{2,4}$", re.I)       # CSL7650, EEL2XXX, MEL7XX0, CSL1xxx
SLOT_CODE_RE = re.compile(r"[A-Z]{1,2}\d{0,2}")                  # A, NG2, M10, L1
SLOT_TOKEN_RE = re.compile(r"\b([A-Z]{1,2}\d{0,2})\b")           # tokens inside "E, M7, M10" / "C (Fixed)"
TIME_RE = re.compile(r"^(\d{1,2})(?::(\d\d))?\s*[–-]\s*(\d{1,2})(?::(\d\d))?$")
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
_TITLES_RE = re.compile(r"\b(dr|prof|professor|mr|mrs|ms)\b\.?", re.I)
_NOT_A_PERSON_RE = re.compile(r"\b(tbd|tba|dept|department|na)\b|\?", re.I)


def _norm(s):
    return re.sub(r"[^a-z0-9/]+", " ", str(s).lower()).strip()


def _norm_header(h):
    return _norm(re.sub(r"\(.*?\)", " ", str(h)))   # "COURSE CODE (CIL)" -> "course code"


def _norm_code(code):
    return re.sub(r"[^A-Z0-9]", "", str(code).upper())


def _clean_person(name):
    """'Dr. Roshan K. Hota' -> 'roshan k hota' (for comparing names)."""
    return " ".join(re.sub(r"[^a-z ]", " ", _TITLES_RE.sub(" ", str(name).lower())).split())


def _read_rows(path):
    """All rows of a CSV with whitespace (incl. line breaks inside cells) collapsed."""
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return [[" ".join(c.split()) for c in row] for row in csv.reader(f)]


def split_people(text):
    """'Dr. Gopal Gote, Dr Nipun Arora & Prof X (FA-2nd Year)' -> ['Gopal Gote', 'Nipun Arora', 'X'].
    Placeholders like 'TBD' or 'ELECTRONICS Dept.' are dropped."""
    people = []
    for part in re.split(r",|&|;|/|\band\b", str(text)):
        p = _TITLES_RE.sub(" ", re.sub(r"\(.*?\)", " ", part))
        p = " ".join(p.split()).strip(" ,")
        if p and not _NOT_A_PERSON_RE.search(p) and re.search(r"[A-Za-z]{2}", p) and p not in people:
            people.append(p)
    return people


def department_for_file(path):
    stem = Path(path).stem
    return config.DEPARTMENT_BY_FILE.get(stem.lower(), stem.replace("_", " ").title())


# ------------------------------------------------------------------ parsing course tables

def _header_map(row):
    """{column index: field} if `row` is a course-table header, else None."""
    m = {}
    for i, cell in enumerate(row):
        h = _norm_header(cell)
        field = next((f for f, aliases in COURSE_ALIASES.items() if h in aliases), None)
        if field and (field not in m.values() or field == "co_instructor"):
            m[i] = field
    if len(m) < 2 or not {"course_code", "course_name"} & set(m.values()):
        return None
    # an unnamed column right after a co-instructor column holds more co-instructors (civil.csv)
    for i in [i for i, f in m.items() if f == "co_instructor"]:
        if i + 1 < len(row) and not row[i + 1]:
            m[i + 1] = "co_instructor"
    return m


@lru_cache(maxsize=None)
def parse_course_table(path):
    """List of course records (dicts) from a timetable-like CSV; [] if it is not one."""
    records, header, header_row, section, prev = [], None, [], "", None
    for row in _read_rows(path):
        cells = [c for c in row if c]
        if not cells:
            continue
        h = _header_map(row)
        if h:
            header, header_row, prev = h, row, None
            continue
        if len(cells) == 1:                          # "UG Programme Elective (PE)", "Note: ..."
            section = cells[0]
            continue
        if header is None:
            continue

        rec, people, remarks = {}, [], []
        for i, cell in enumerate(row):
            if not cell:
                continue
            field = header.get(i)
            if field in ("instructor", "co_instructor"):
                people.append(cell)
            elif field:
                rec.setdefault(field, cell)
            elif i < len(header_row) and header_row[i]:
                continue                             # a known-but-unused column such as "Sr No"
            elif CODE_RE.match(cell) and not rec.get("course_code"):
                rec["course_code"] = cell            # code in a column without a header
            else:
                remarks.append(cell)                 # e.g. "For backlog students (Old curriculum)"

        if not rec.get("course_name"):
            if prev and (people or rec.get("course_code")):
                rec["course_name"] = prev["course_name"]   # another instructor/code for the course above
            else:
                continue

        names = split_people(", ".join(people))
        rec["instructor"] = ", ".join(names) if names else ", ".join(people)   # keep "TBD" etc. as written
        if rec.get("course_type"):
            code = rec["course_type"].upper()
            rec["course_type"] = f"{code} ({TYPE_NAMES[code]})" if code in TYPE_NAMES else rec["course_type"]
        elif re.search(r"\belec", f"{rec.get('program', '')} {section}", re.I):
            rec["course_type"] = "Elective"          # cse.csv marks electives in the Batch column
        rec.setdefault("department", department_for_file(path))
        if remarks:
            rec["remarks"] = "; ".join(remarks)
        if section:
            rec["section"] = section
        rec["source"] = Path(path).name
        records.append(rec)
        prev = rec
    return records


def merge_records(records):
    """The same course listed once per programme (civil.csv) -> one record, programmes joined."""
    merged = {}
    for r in records:
        key = (_norm_code(r.get("course_code", "")), _norm(r.get("course_name", "")), r.get("instructor", ""))
        if key not in merged:
            merged[key] = dict(r)
            continue
        m = merged[key]
        for k, v in r.items():
            if not v:
                continue
            have = [x for x in str(m.get(k, "")).split(", ") if x]
            # compare item by item: "A, B" must not be appended again to "A, B" (or to "A, B, A, B")
            new = [x for x in str(v).split(", ") if x and x not in have]
            if new:
                m[k] = ", ".join(have + new)
    return list(merged.values())


# ------------------------------------------------------------------ slot timings

def _fmt_time(text):
    """'1–1:50' -> '13:00-13:50' (afternoon hours are written without pm in the grid)."""
    h1, m1, h2, m2 = TIME_RE.match(text).groups()
    h1, h2 = int(h1), int(h2)
    h1, h2 = (h1 + 12 if h1 < 8 else h1), (h2 + 12 if h2 < 8 else h2)
    return f"{h1:02d}:{m1 or '00'}-{h2:02d}:{m2 or '00'}"


@lru_cache(maxsize=None)
def parse_slot_grid(path):
    """{slot: ['Tue 11:00-11:50', ...]} from a weekly grid; {} if the file is not one."""
    times, day_cols = {}, None
    for row in _read_rows(path):
        if day_cols is None:
            cols = {i: c[:3].title() for i, c in enumerate(row) if len(c) <= 9 and c[:3].title() in DAYS}
            if len(cols) >= 3:
                day_cols = cols
            continue
        if not row or not TIME_RE.match(row[0]):
            if times:
                break                                # the grid has ended (notes follow)
            continue
        t = _fmt_time(row[0])
        for i, day in day_cols.items():
            for j in (i, i + 1):                     # the slot under the day + the lab slot next to it
                if j < len(row) and SLOT_CODE_RE.fullmatch(row[j]):
                    times.setdefault(row[j], []).append(f"{day} {t}")
    return times


@lru_cache(maxsize=1)
def slot_times():
    times = {}
    for path in sorted(config.KB_DIR.rglob("*.csv")):
        for slot, t in parse_slot_grid(path).items():
            times.setdefault(slot, []).extend(t)
    # Mon..Sat order, then by time ("Mon 11:00-11:50, Wed 11:00-11:50, Fri 10:00-10:50")
    return {s: sorted(t, key=lambda x: (DAYS.index(x[:3]), x[4:])) for s, t in times.items()}


def slot_grid_files():
    return [p.name for p in sorted(config.KB_DIR.rglob("*.csv")) if parse_slot_grid(p)]


def slot_query(text):
    """'D', 'slot D', 'Slot M7' -> 'D' / 'M7' if it is a slot of the slot grid, else None."""
    m = re.fullmatch(r"(?:slot\s+)?([A-Za-z]{1,2}\d{0,2})(?:\s+slot)?", str(text).strip(), re.I)
    return m.group(1).upper() if m and m.group(1).upper() in slot_times() else None


def timings_for(slot_text):
    """'E, M7, M10' -> 'E: Tue 11:00-11:50, ...; M7: ...' (only slots found in the slot grid)."""
    grid = slot_times()
    slots = dict.fromkeys(SLOT_TOKEN_RE.findall(str(slot_text)))
    return "; ".join(f"{s}: {', '.join(grid[s])}" for s in slots if s in grid)


# ------------------------------------------------------------------ loading everything

def _read_faculty(path):
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding_errors="replace")
    df.columns = [str(c).strip() for c in df.columns]
    cols = {}
    for field, aliases in FACULTY_ALIASES.items():
        col = next((c for c in df.columns if _norm_header(c) in aliases), None)
        if col is None:
            return None
        cols[col] = field
    df = df.rename(columns=cols)
    df["source"] = Path(path).name
    return df


@lru_cache(maxsize=1)
def load_tables():
    """Return (courses_df, faculty_df) for all CSVs in the knowledge base."""
    course_records, faculty_frames = [], []
    for path in sorted(config.KB_DIR.rglob("*.csv")):
        try:
            records = parse_course_table(path)
            if records:
                course_records.extend(records)
                continue
            fac = _read_faculty(path)
            if fac is not None:
                faculty_frames.append(fac)
        except Exception as e:
            print(f"[csv_store] could not read {path.name}: {e}")

    courses = pd.DataFrame(merge_records(course_records))
    for field in list(COURSE_ALIASES) + ["remarks", "section", "source"]:
        if field not in courses:
            courses[field] = ""
    courses = courses.fillna("")
    faculty = pd.concat(faculty_frames, ignore_index=True).fillna("") if faculty_frames else pd.DataFrame()
    return courses, faculty


def _row_to_dict(row):
    return {k: v for k, v in row.items() if str(v).strip()}


# ------------------------------------------------------------------ lookups

# abbreviations that are not simply the initials of the course name
_ABBREVIATIONS = {"dbms": "database"}


def _initials(name):
    """"Data Structures and Algorithms" -> "dsa" (small words are skipped)."""
    return "".join(w[0] for w in _norm(name).split() if w not in {"and", "of", "the", "in", "for", "to"})


def find_course(query):
    """Match by course code first (exact, ignoring spaces), then by abbreviation, name substring, fuzzy."""
    courses, _ = load_tables()
    if courses.empty:
        return []

    code = _norm_code(query)
    by_code = courses[courses["course_code"].map(_norm_code) == code]
    if code and not by_code.empty:
        return [_row_to_dict(r) for _, r in by_code.iterrows()]

    q = _norm(query)
    q = _ABBREVIATIONS.get(q, q)
    names = courses["course_name"].map(_norm)

    # abbreviations students use: "DSA", "OS", "COA" are the initials of the course name.
    # Checked before the substring match, otherwise "se" would match "databaSE ..."
    if " " not in q and 2 <= len(q) <= 6:
        by_abbr = courses[courses["course_name"].map(_initials) == q]
        if not by_abbr.empty:
            return [_row_to_dict(r) for _, r in by_abbr.iterrows()]

    # (a 1-2 letter query would be "contained" in almost every course name)
    by_name = courses[names.str.contains(re.escape(q), regex=True)] if len(q) >= 3 else courses.iloc[0:0]
    if not by_name.empty:
        return [_row_to_dict(r) for _, r in by_name.iterrows()]

    # fuzzy fallback for typos like "autonomus systems"
    scores = names.map(lambda n: SequenceMatcher(None, q, n).ratio())
    best = scores[scores >= 0.75]
    return [_row_to_dict(courses.loc[i]) for i in best.sort_values(ascending=False).index[:3]]


def find_email(person):
    """Faculty email by name. Tolerates titles, middle names/initials and small spelling
    differences ('Roshan K Hota' = 'Roshan Kumar Hota', 'Majumder' = 'Mazumder')."""
    _, faculty = load_tables()
    target = _clean_person(person).split()
    if faculty.empty or not target:
        return []
    exact, close = [], []
    for _, r in faculty.iterrows():
        cand = _clean_person(r["name"]).split()
        if not cand:
            continue
        hit = {"name": r["name"], "email": r["email"], "source": r["source"]}
        if cand == target:
            exact.append(hit)
        elif cand[0] == target[0] and (len(cand) == 1 or len(target) == 1
                                       or SequenceMatcher(None, cand[-1], target[-1]).ratio() >= 0.85):
            close.append(hit)
    # a close match is only trusted when it is unambiguous (never guess an email ID)
    return exact or (close if len(close) == 1 else [])


# words the LLM likes to add ("Humanities department", "elective courses") that never appear in the CSV values
_FILLER = {"department", "dept", "of", "and", "the", "school", "centre", "center", "course", "courses"}


def _words_match(query, value):
    """True if every meaningful word of `query` occurs in `value`; plurals also match
    ("electives" matches "Elective"). An empty query matches everything."""
    val = _norm(value)
    words = [w for w in _norm(query).split() if w not in _FILLER]
    return all(w in val or (w.endswith("s") and w[:-1] in val) for w in words)


def _department_match(query, department):
    q = " ".join(w for w in _norm(query).split() if w not in _FILLER)
    aliases = [_norm(a) for a in config.DEPARTMENT_ALIASES.get(department, [])]
    return (not q or _words_match(q, department) or q.replace(" ", "") == _initials(department)
            or q in aliases)


def departments():
    courses, _ = load_tables()
    return sorted(d for d in courses["department"].unique() if d) if not courses.empty else []


def has_department(query):
    return any(_department_match(query, d) for d in departments())


def is_department(query):
    """True if `query` names a department ('CSE', 'civil', 'department=Civil') rather than a course."""
    q = re.sub(r"^\s*(department|dept)\s*[=:]\s*", "", str(query), flags=re.I)
    q = " ".join(w for w in _norm(q).split() if w not in _FILLER)
    return bool(q) and has_department(q)


def _level_of(code):
    """CSL7650 -> '7', HSL4010 -> '4'. The first digit of the numeric part gives the level."""
    m = re.search(r"\d", str(code))
    return m.group(0) if m else ""


def count_courses(department, level, course_type):
    """Filter the course table; empty string means 'no filter' for that field."""
    courses, _ = load_tables()
    if courses.empty:
        return []
    # one row per distinct course. A real code identifies a course; a missing or placeholder code
    # (EEL2XXX, MEL7XX0 - shared by different courses) does not, then department + name is used
    def course_key(r):
        code = r["course_code"]
        real = bool(code) and "X" not in code.upper()
        return code.upper() if real else f"{r['department']}|{_norm(r['course_name'])}"
    df = courses.assign(_key=courses.apply(course_key, axis=1)).drop_duplicates(subset=["_key"]).drop(columns="_key")

    if department.strip():
        df = df[df["department"].map(lambda d: _department_match(department, d))]
    if level.strip():
        digit = re.search(r"\d", level)
        if digit:
            df = df[df["course_code"].map(_level_of) == digit.group(0)]
    if course_type.strip():
        df = df[df["course_type"].map(lambda t: _words_match(course_type, t))]

    return [_row_to_dict(r) for _, r in df.iterrows()]
