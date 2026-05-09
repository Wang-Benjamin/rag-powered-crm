"""
Chunking - sentence-aware text splitter for embedding long documents.

Splits long inputs (call transcripts, multi-paragraph emails, long notes)
into overlapping windows so each chunk fits comfortably under the embedding
model's input limit and so needle-in-haystack queries can hit a tightly
focused span instead of a diluted whole-doc vector.

Tuned for OpenAI text-embedding-3-small (8K input limit). Default windows
target ~500 tokens with ~50-token overlap, which empirically maximises
recall on conversational CRM content (notes/emails/transcripts) while
keeping embedding cost roughly proportional to the doc length.
"""

import re
from dataclasses import dataclass
from typing import List, Optional


# A token is roughly 4 chars for English; we use this throughout to avoid
# pulling in tiktoken as a hard dep. The chunker only needs an order-of-
# magnitude estimate to pick window sizes.
_CHARS_PER_TOKEN = 4

DEFAULT_TARGET_TOKENS = 500
DEFAULT_OVERLAP_TOKENS = 50
MIN_CHUNK_TOKENS = 30   # discard chunks shorter than this (mostly footers)


# Sentence-end finder: handles ., !, ?, plus newline-terminated lines.
# We deliberately don't try to be clever about abbreviations — for CRM
# content (notes/emails) the small fraction of false splits is harmless
# because adjacent chunks have overlap.
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9])|\n{2,}')


@dataclass
class Chunk:
    """A single chunk of a parent document."""
    idx: int
    content: str

    @property
    def char_len(self) -> int:
        return len(self.content)

    @property
    def approx_tokens(self) -> int:
        return max(1, self.char_len // _CHARS_PER_TOKEN)


def _split_sentences(text: str) -> List[str]:
    """Split text into sentence-ish units. Keeps punctuation."""
    if not text:
        return []
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    return [p.strip() for p in parts if p and p.strip()]


def chunk_text(
    text: str,
    target_tokens: int = DEFAULT_TARGET_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> List[Chunk]:
    """
    Split `text` into overlapping sentence-aligned chunks.

    Returns at least one chunk for any non-empty input. For inputs smaller
    than `target_tokens`, returns the input as a single chunk (no splitting
    overhead, no overlap waste).
    """
    if not text or not text.strip():
        return []

    text = text.strip()
    target_chars = target_tokens * _CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * _CHARS_PER_TOKEN

    if len(text) <= target_chars:
        return [Chunk(idx=0, content=text)]

    sentences = _split_sentences(text)
    if not sentences:
        # No sentence boundaries found — fall back to char-window slicing.
        return _chunk_by_chars(text, target_chars, overlap_chars)

    chunks: List[Chunk] = []
    buffer: List[str] = []
    buffer_len = 0
    idx = 0

    for sent in sentences:
        sent_len = len(sent) + 1  # +1 for the joining space
        if buffer and buffer_len + sent_len > target_chars:
            content = ' '.join(buffer).strip()
            if len(content) >= MIN_CHUNK_TOKENS * _CHARS_PER_TOKEN:
                chunks.append(Chunk(idx=idx, content=content))
                idx += 1
            # Seed next buffer with overlap from end of previous buffer.
            buffer, buffer_len = _build_overlap_buffer(buffer, overlap_chars)

        buffer.append(sent)
        buffer_len += sent_len

    # Flush trailing buffer.
    if buffer:
        content = ' '.join(buffer).strip()
        if content and (len(content) >= MIN_CHUNK_TOKENS * _CHARS_PER_TOKEN or not chunks):
            chunks.append(Chunk(idx=idx, content=content))

    return chunks or [Chunk(idx=0, content=text)]


def _build_overlap_buffer(prev_buffer: List[str], overlap_chars: int) -> tuple[List[str], int]:
    """Take the last sentences from prev_buffer up to overlap_chars chars."""
    if overlap_chars <= 0 or not prev_buffer:
        return [], 0

    overlap: List[str] = []
    overlap_len = 0
    for sent in reversed(prev_buffer):
        sent_len = len(sent) + 1
        if overlap_len + sent_len > overlap_chars and overlap:
            break
        overlap.insert(0, sent)
        overlap_len += sent_len
    return overlap, overlap_len


def _chunk_by_chars(text: str, target_chars: int, overlap_chars: int) -> List[Chunk]:
    """Fallback char-window chunker for inputs with no sentence boundaries."""
    chunks: List[Chunk] = []
    step = max(1, target_chars - overlap_chars)
    idx = 0
    pos = 0
    while pos < len(text):
        end = min(pos + target_chars, len(text))
        content = text[pos:end].strip()
        if content:
            chunks.append(Chunk(idx=idx, content=content))
            idx += 1
        if end == len(text):
            break
        pos += step
    return chunks


def chunk_email(subject: Optional[str], body: Optional[str], **kw) -> List[Chunk]:
    """Chunk an email; subject is prepended once to chunk 0 only."""
    body_text = (body or '').strip()
    chunks = chunk_text(body_text, **kw) if body_text else []
    if subject:
        prefix = f"Subject: {subject.strip()}\n\n"
        if chunks:
            chunks[0] = Chunk(idx=0, content=prefix + chunks[0].content)
        else:
            chunks = [Chunk(idx=0, content=f"Subject: {subject.strip()}")]
    return chunks


def chunk_note(title: Optional[str], body: Optional[str], **kw) -> List[Chunk]:
    """Chunk a note; title is prepended once to chunk 0 only."""
    body_text = (body or '').strip()
    chunks = chunk_text(body_text, **kw) if body_text else []
    if title:
        prefix = f"{title.strip()}\n\n"
        if chunks:
            chunks[0] = Chunk(idx=0, content=prefix + chunks[0].content)
        else:
            chunks = [Chunk(idx=0, content=title.strip())]
    return chunks
