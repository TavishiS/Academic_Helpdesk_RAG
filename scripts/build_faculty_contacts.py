"""
(Re)build faculty_contacts.csv from the instructors listed in the course CSVs
(used by `make faculty-contacts`), so the contacts always match the timetables.

The timetables only give names, so emails and phone numbers are FAKE:
  - emails use the reserved ".example" domain (can never be a real address)
  - phone numbers are 10 digits starting with 2-5 (Indian mobiles start with 6-9)
Both are derived from a hash of the name, so a person keeps the same fake
contact details every time the file is rebuilt.

The same person is sometimes written differently ("Roshan K Hota" /
"Roshan Kumar Hota", "Pratik Majumder" / "Pratik Mazumder", "Kunwar" /
"Kunwar Aditya"); such variants are merged and printed for checking.

  python scripts/build_faculty_contacts.py
"""
import csv
import hashlib
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from helpdesk import csv_store  # noqa: E402

OUT = config.KB_DIR / "faculty_contacts.csv"


def same_person(a, b):
    """Same first name, and same (or almost same) last name; a one-word name matches on first name."""
    ta, tb = csv_store._clean_person(a).split(), csv_store._clean_person(b).split()
    if not ta or not tb or ta[0] != tb[0]:
        return False
    return len(ta) == 1 or len(tb) == 1 or SequenceMatcher(None, ta[-1], tb[-1]).ratio() >= 0.85


def fake_phone(name, taken):
    salt = 0
    while True:
        h = int(hashlib.sha256(f"{name.lower()}#{salt}".encode()).hexdigest(), 16)
        phone = str(2 + h % 4) + str(h // 4)[-9:].zfill(9)
        if phone not in taken:
            return phone
        salt += 1


def main():
    # every (person, department) occurrence in the course tables
    seen = []
    for path in sorted(config.KB_DIR.rglob("*.csv")):
        for rec in csv_store.parse_course_table(path):
            for person in csv_store.split_people(rec.get("instructor", "")):
                seen.append((person, rec["department"]))
    if not seen:
        sys.exit(f"No instructors found in the course CSVs of {config.KB_DIR}")

    # group spelling variants; multi-word names first so that "Kunwar" can join "Kunwar Aditya"
    groups = []
    for person in sorted({p for p, _ in seen}, key=lambda p: -len(p.split())):
        matches = [g for g in groups if any(same_person(person, v) for v in g)]
        if len(matches) == 1:
            matches[0].add(person)
        else:                        # no match, or ambiguous (e.g. two people called "Kunwar ...")
            groups.append({person})

    rows, taken = [], set()
    for variants in groups:
        counts = Counter(p for p, _ in seen if p in variants)
        name = max(variants, key=lambda v: (counts[v], len(v)))      # most used spelling, then the longest
        dept = Counter(d for p, d in seen if p in variants).most_common(1)[0][0]
        email = ".".join(csv_store._clean_person(name).split()) + "@iitj.example"
        phone = fake_phone(name, taken)
        taken.add(phone)
        rows.append({"Name": name, "Department": dept, "Email": email, "Phone": phone})
        if len(variants) > 1:
            print(f"  merged spellings -> {name}: {sorted(variants - {name})}")

    rows.sort(key=lambda r: (r["Department"], r["Name"]))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Name", "Department", "Email", "Phone"])
        w.writeheader()
        w.writerows(rows)
    per_dept = Counter(r["Department"] for r in rows)
    print(f"==> Wrote {len(rows)} faculty to {OUT.relative_to(config.ROOT)}: "
          + ", ".join(f"{d} {n}" for d, n in sorted(per_dept.items())))


if __name__ == "__main__":
    main()
