"""
Ingestion: load documents -> split into chunks -> embed -> store in ChromaDB.

Supported formats: .pdf (page by page), .txt, .csv (rows converted to text).
Run with:  python main.py ingest
"""
import re
from pathlib import Path

import config
from helpdesk import csv_store, retriever


# ------------------------------------------------------------------ loaders
# Each loader yields (text, metadata) pairs. Metadata is what we later use for citations.

def load_pdf(path):
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    for i, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if text.strip():
            yield text, {"page": i + 1}
    # NOTE: scanned PDFs have no text layer -> nothing is extracted (would need OCR)


def load_txt(path):
    yield path.read_text(encoding="utf-8", errors="replace"), {}


# labels used when a course record is written out as text for embedding
_RECORD_LABELS = {
    "course_code": "Course Code", "course_name": "Course Name", "department": "Department",
    "instructor": "Instructor", "slot": "Slot", "timings": "Class timings", "lab_slot": "Lab Slot",
    "credits": "Credits", "ltp": "L-T-P", "course_type": "Course Type", "program": "Program",
    "year": "Year", "section": "Section", "remarks": "Remarks",
}


def _csv_lines(path):
    """One line of text per table row. Timetables are read with csv_store's parser (the same one
    the lookup tools use), so messy exports with section titles and repeated headers come out clean."""
    records = csv_store.parse_course_table(path)
    if records:
        lines = []
        for r in csv_store.merge_records(records):
            r = dict(r, timings=csv_store.timings_for(f"{r.get('slot', '')} {r.get('lab_slot', '')}"))
            lines.append(" | ".join(f"{label}: {r[k]}" for k, label in _RECORD_LABELS.items() if r.get(k)))
        return lines

    rows = [row for row in csv_store._read_rows(path) if any(row)]
    grid = csv_store.parse_slot_grid(path)
    if grid:
        # a weekly slot grid: "Slot E: Tue 11:00-11:50, ..." is what a student asks about;
        # the raw rows (notes, slot allocation rules) are added as plain text
        return ([f"Slot {s}: {', '.join(t)}" for s, t in grid.items()]
                + [" | ".join(c for c in row if c) for row in rows])

    # any other table (e.g. faculty contacts): 'column: value' pairs under the first header row
    header, lines = rows[0] if rows else [], []
    for row in rows[1:]:
        lines.append(" | ".join(f"{header[i]}: {c}" if i < len(header) and header[i] else c
                                for i, c in enumerate(row) if c))
    return lines


def load_csv(path):
    """
    A CSV row like (CSL7650, Autonomous Systems, E) is meaningless to an embedding
    model on its own, so every row is written as 'column: value' text and a few
    rows are grouped into one chunk.
    """
    lines = _csv_lines(path)
    n = config.CSV_ROWS_PER_CHUNK
    for start in range(0, len(lines), n):
        block = lines[start:start + n]
        yield "\n".join(block), {"rows": f"{start + 1}-{start + len(block)}", "is_table": True}


LOADERS = {".pdf": load_pdf, ".txt": load_txt, ".csv": load_csv}


# ------------------------------------------------------------------ chunking

def _split_units(text, size):
    """Break text into paragraphs, then sentences, then hard-cut anything still too long."""
    units = []
    for para in re.split(r"\n\s*\n", text):
        para = " ".join(para.split())  # collapse whitespace / line breaks from PDFs
        if not para:
            continue
        if len(para) <= size:
            units.append(para)
            continue
        for sent in re.split(r"(?<=[.!?;:])\s+", para):
            while len(sent) > size:
                units.append(sent[:size])
                sent = sent[size:]
            if sent:
                units.append(sent)
    return units


def chunk_text(text, size=None, overlap=None):
    """
    Greedy packing of paragraphs/sentences into chunks of at most `size` chars.
    The last few sentences of a chunk are repeated at the start of the next one
    (overlap) so that a rule split across a boundary is still retrievable.
    """
    size = size or config.CHUNK_SIZE
    overlap = config.CHUNK_OVERLAP if overlap is None else overlap

    chunks, current, cur_len = [], [], 0
    for unit in _split_units(text, size):
        if current and cur_len + len(unit) + 1 > size:
            chunks.append(" ".join(current))
            # carry over trailing units that fit in the overlap budget
            tail, tail_len = [], 0
            for u in reversed(current):
                if tail_len + len(u) + 1 > overlap:
                    break
                tail.insert(0, u)
                tail_len += len(u) + 1
            current, cur_len = tail, tail_len
        current.append(unit)
        cur_len += len(unit) + 1
    if current:
        chunks.append(" ".join(current))
    return [c for c in chunks if len(c) > 30]  # drop headers/page numbers etc.


# ------------------------------------------------------------------ pipeline

def build_chunks(kb_dir):
    files = sorted(p for p in Path(kb_dir).rglob("*") if p.suffix.lower() in config.SUPPORTED_EXTENSIONS)
    all_chunks = []
    for path in files:
        loader = LOADERS[path.suffix.lower()]
        n_before = len(all_chunks)
        try:
            for text, meta in loader(path):
                # table blocks are already small and row-aligned, don't re-split them
                pieces = [text] if meta.get("is_table") else chunk_text(text)
                for piece in pieces:
                    m = {"source": path.name, "file_type": path.suffix.lower()[1:]}
                    m.update({k: v for k, v in meta.items() if k != "is_table"})
                    all_chunks.append((piece, m))
        except Exception as e:
            print(f"  [skip] {path.name}: {e}")
            continue
        print(f"  {path.name:<45} {len(all_chunks) - n_before:>4} chunks")
    return files, all_chunks


def ingest(kb_dir=None):
    kb_dir = Path(kb_dir or config.KB_DIR)
    print(f"Loading documents from {kb_dir}")
    files, chunks = build_chunks(kb_dir)
    if not chunks:
        print("No supported documents found (.pdf/.txt/.csv). Nothing to index.")
        return

    # start fresh every time so deleted/edited files don't leave stale chunks behind
    client = retriever.get_client()
    try:
        client.delete_collection(config.COLLECTION_NAME)
    except Exception:
        pass
    collection = retriever.get_collection(create=True)

    # The file name is prepended before embedding (e.g. "attendance_policy") because it
    # is often the strongest hint about what a chunk is about. The stored document stays clean.
    texts = [c for c, _ in chunks]
    to_embed = [f"Document: {Path(m['source']).stem.replace('_', ' ')}\n{c}" for c, m in chunks]
    print(f"Embedding {len(texts)} chunks with {config.EMBED_MODEL} ...")
    vectors = retriever.embed_passages(to_embed)

    ids = [f"{m['source']}::{m.get('page', m.get('rows', 0))}::{i}" for i, (_, m) in enumerate(chunks)]
    batch = 500
    for s in range(0, len(ids), batch):
        collection.add(ids=ids[s:s + batch], documents=texts[s:s + batch],
                       embeddings=vectors[s:s + batch], metadatas=[m for _, m in chunks[s:s + batch]])

    print(f"Indexed {len(ids)} chunks from {len(files)} files into '{config.COLLECTION_NAME}' "
          f"({config.CHROMA_DIR})")
