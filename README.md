# Chunking & Cleaning Pipeline

A text cleaning and sentence-boundary chunking pipeline built for Greek legal documents. Designed to prepare court rulings for embedding and vector search — but the approach generalises to any formal legal corpus.

---

## The Problem with Naive Chunking

The obvious approach to chunking long documents is to split them mechanically every N tokens:

```
[token 0 → 2000] → chunk 1
[token 2000 → 4000] → chunk 2
...
```

For legal text, this is a disaster. Court rulings are dense with citations, article references, and multi-clause sentences. A mechanical split cuts straight through them:

```
# chunk 1 ends with:
"...σύμφωνα με το άρθρο 8 παρ. 2 του Ν."

# chunk 2 starts with:
"2112/1920, η αποζημίωση υπολογίζεται..."
```

The citation is split across two chunks. Neither chunk makes sense on its own. The embedding of chunk 1 carries half a legal reference with no meaning, and chunk 2 opens with a dangling clause. Both will retrieve poorly.

The solution is to split on **sentence boundaries** instead — keep each sentence whole, and accumulate sentences into chunks until the token limit is reached.

---

## How It Works

The pipeline runs in two stages: **clean** then **chunk**. `pipeline.py` orchestrates both against a Postgres database of cases.

### Stage 1 — Cleaning (`cleaner.py`)

Four steps applied in order:

**1. Strip footers** — Every Greek court ruling ends with the same boilerplate closing lines (the judge's signature block, publication notice, decision line). These appear on every single case and carry no legal meaning. They're stripped before anything else so they don't pollute chunks.

Example of what gets stripped:
```
ΚΡΙΘΗΚΕ, αποφασίσθηκε στην Αθήνα, στις 8 Ιανουαρίου 2020.
ΔΗΜΟΣΙΕΥΘΗΚΕ σε δημόσια συνεδρίαση στο ακροατήριό του...
H ΑΝΤΙΠΡΟΕΔΡΟΣ    Η ΓΡΑΜΜΑΤΕΑΣ
```

**2. Normalize whitespace** — HTML extraction often produces 3–5 consecutive blank lines between paragraphs. These are collapsed to a single blank line. Paragraph boundaries are preserved because the chunker uses them as natural split points.

**3. Clean lines** — Each line is stripped of leading/trailing whitespace, and internal runs of multiple spaces are collapsed to one.

**4. Final strip** — Trims any remaining leading/trailing whitespace from the full document.

---

### Stage 2 — Chunking (`chunker.py`)

Token limits:
- `CHUNK_MAX_TOKENS = 2000` — a chunk never exceeds this
- `CHUNK_MIN_TOKENS = 150` — chunks below this are merged into the previous one

**Algorithm:**

1. Split the document into sentences using a regex tuned for Greek legal text — splits on `. ` or `.\n` followed by an uppercase letter or digit. The period stays attached to the sentence it closes.

2. Accumulate sentences into the current chunk until adding the next sentence would exceed `CHUNK_MAX_TOKENS`. When that happens, flush the current chunk and start a new one.

3. If a single sentence exceeds `CHUNK_MAX_TOKENS` on its own (rare, but happens with long citation blocks), it is force-split at token boundaries as a fallback. This is the only case where a cut happens mid-sentence.

4. After all sentences are processed, if the final chunk is below `CHUNK_MIN_TOKENS`, it is merged into the previous chunk — prevents tiny trailing fragments from becoming their own chunk.

**Output** — each chunk is a dict:
```python
{
    "case_id":     int,    # foreign key to the cases table
    "chunk_index": int,    # position within the case (0-indexed)
    "text":        str,    # the chunk text
    "token_count": int,    # pre-computed token count
}
```

---

### Stage 3 — Orchestration (`pipeline.py`)

Pulls all cases from Postgres that have not yet been chunked, runs clean → chunk on each, and bulk inserts the results into the `chunks` table. Idempotent — safe to re-run, will only process new cases.

```bash
python pipeline/pipeline.py
```

---

## Configuration

| Constant | Default | Description |
|---|---|---|
| `CHUNK_MAX_TOKENS` | `2000` | Maximum tokens per chunk |
| `CHUNK_MIN_TOKENS` | `150` | Minimum tokens — smaller chunks are merged |

Tokenisation uses `cl100k_base` (the same tokeniser as `text-embedding-3-large`) so token counts are exact relative to the embedding model.

---

## Dependencies

```
tiktoken
psycopg2-binary
```
