# pipeline/chunker.py
import re
import tiktoken

CHUNK_MAX_TOKENS = 2000   # never exceed this
CHUNK_MIN_TOKENS = 150    # merge chunks below this into the next one

_enc = tiktoken.get_encoding("cl100k_base")


def _token_count(text: str) -> int:
    return len(_enc.encode(text))


def _split_sentences(text: str) -> list[str]:
    """
    Split Greek legal text into sentences.
    Splits on '. ' or '.\n' followed by an uppercase letter or digit,
    which is the consistent pattern in Greek court rulings.
    Keeps the period attached to the sentence it closes.
    """
    parts = re.split(r'(?<=\.)\s+(?=[Α-ΩΆΈΉΊΌΎΏA-ZA-Z0-9«\(])', text)
    return [p.strip() for p in parts if p.strip()]


def _force_split(text: str) -> list[str]:
    """
    Force-split a text that exceeds CHUNK_MAX_TOKENS by cutting at token boundaries.
    Used as a fallback when a single 'sentence' is too large to fit in one chunk.
    """
    tokens = _enc.encode(text)
    parts = []
    for i in range(0, len(tokens), CHUNK_MAX_TOKENS):
        parts.append(_enc.decode(tokens[i:i + CHUNK_MAX_TOKENS]))
    return parts


def chunk(text: str, case_id: int) -> list[dict]:
    """
    Split a cleaned case text into sentence-boundary chunks.

    Strategy:
    - Split the text into sentences first
    - Accumulate sentences into a chunk until CHUNK_MAX_TOKENS is reached
    - If a single sentence exceeds CHUNK_MAX_TOKENS, force-split it by tokens
    - If the final chunk is below CHUNK_MIN_TOKENS, merge it into the previous one
    - Never cut mid-sentence unless the sentence itself is too large
    """
    sentences = _split_sentences(text)

    chunks = []
    current_sentences = []
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = _token_count(sentence)

        # Single sentence too large — flush current, force-split the sentence
        if sentence_tokens > CHUNK_MAX_TOKENS:
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_tokens = 0
            chunks.extend(_force_split(sentence))
            continue

        # Adding this sentence would exceed max — flush first
        if current_tokens + sentence_tokens > CHUNK_MAX_TOKENS and current_sentences:
            chunks.append(" ".join(current_sentences))
            current_sentences = []
            current_tokens = 0

        current_sentences.append(sentence)
        current_tokens += sentence_tokens

    # Flush the last chunk
    if current_sentences:
        chunks.append(" ".join(current_sentences))

    # Merge any trailing chunk that is too small into the previous one
    if len(chunks) > 1 and _token_count(chunks[-1]) < CHUNK_MIN_TOKENS:
        chunks[-2] = chunks[-2] + " " + chunks[-1]
        chunks.pop()

    return [
        {
            "case_id":     case_id,
            "chunk_index": i,
            "text":        chunk_text,
            "token_count": _token_count(chunk_text),
        }
        for i, chunk_text in enumerate(chunks)
    ]
