"""Chunk RateMyProfessors plaintext files for the retrieval pipeline."""

from __future__ import annotations

import json
import re
from pathlib import Path


DOCUMENTS_DIR = "documents"
OUTPUT_FILE = "chunks.json"
CHUNK_SIZE = 500
OVERLAP = 75
MIN_LENGTH = 50

BLOCK_SPLIT_RE = re.compile(r"(?:\r?\n){2,}")
COURSE_LINE_RE = re.compile(
    r"^Course:\s*(.*?)\s*\|\s*Quality:\s*(.*?)\s*\|\s*Difficulty:\s*(.*?)\s*$"
)


def _clean_lines(text: str) -> list[str]:
    """Return non-empty lines with surrounding whitespace removed."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def _source_prefix(source_file: str) -> str:
    """Create a stable chunk id prefix from a source filename."""
    stem = Path(source_file).stem.lower()
    return re.sub(r"[^a-z0-9]+", "_", stem).strip("_")


def _professor_id_from_filename(source_file: str) -> str:
    match = re.match(r"^(\d+)", Path(source_file).stem)
    return match.group(1) if match else Path(source_file).stem


def _parse_professor_name(header_block: str, fallback: str) -> str:
    for line in _clean_lines(header_block):
        if line.startswith("Professor:"):
            return line.partition(":")[2].strip() or fallback
    return fallback


def _parse_review_block(review_block: str) -> dict[str, str]:
    lines = _clean_lines(review_block)
    course = "N/A"
    quality = "N/A"
    difficulty = "N/A"
    tags = "N/A"
    review = ""

    if lines:
        match = COURSE_LINE_RE.match(lines[0])
        if match:
            course, quality, difficulty = (part.strip() for part in match.groups())

    for index, line in enumerate(lines):
        if line.startswith("Tags:"):
            tags = line.partition(":")[2].strip() or "N/A"
        elif line.startswith("Review:"):
            first_review_line = line.partition(":")[2].strip()
            remaining_review_lines = lines[index + 1 :]
            review = "\n".join([first_review_line, *remaining_review_lines]).strip()
            break

    return {
        "course": course,
        "quality": quality,
        "difficulty": difficulty,
        "tags": tags,
        "review": review,
    }


def _format_review_text(review: dict[str, str]) -> str:
    return (
        f"Course: {review['course']} | Quality: {review['quality']} | "
        f"Difficulty: {review['difficulty']}\n"
        f"Tags: {review['tags']}\n"
        f"Review: {review['review']}"
    ).strip()


def _make_chunk(
    *,
    chunk_text: str,
    chunk_id: str,
    professor: str,
    professor_id: str,
    source_file: str,
    review: dict[str, str],
) -> dict[str, str]:
    return {
        "chunk_id": chunk_id,
        "text": chunk_text,
        "professor": professor,
        "professor_id": professor_id,
        "source_file": source_file,
        "course": review["course"],
        "quality": review["quality"],
        "difficulty": review["difficulty"],
        "tags": review["tags"],
    }


def chunk_review_block(
    review_block: str,
    professor: str,
    professor_id: str,
    source_file: str,
    chunk_id_prefix: str,
    first_chunk_number: int = 0,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP,
    min_length: int = MIN_LENGTH,
) -> list[dict[str, str]]:
    """Turn one review block into one or more chunks.

    Reviews stay isolated from each other. If a future review is longer than the
    target size, only that review text is split with overlap.
    """
    review = _parse_review_block(review_block)
    chunk_text = _format_review_text(review)

    if len(chunk_text) <= chunk_size:
        if len(chunk_text) < min_length:
            return []
        return [
            _make_chunk(
                chunk_text=chunk_text,
                chunk_id=f"{chunk_id_prefix}_{first_chunk_number}",
                professor=professor,
                professor_id=professor_id,
                source_file=source_file,
                review=review,
            )
        ]

    prefix = (
        f"Course: {review['course']} | Quality: {review['quality']} | "
        f"Difficulty: {review['difficulty']}\n"
        f"Tags: {review['tags']}\n"
        "Review: "
    )
    available = max(1, chunk_size - len(prefix))
    step = max(1, available - overlap)

    chunks = []
    start = 0
    counter = first_chunk_number
    review_text = review["review"]
    while start < len(review_text):
        end = start + available
        segment = review_text[start:end].strip()
        split_chunk_text = f"{prefix}{segment}".strip()

        if len(split_chunk_text) >= min_length:
            chunks.append(
                _make_chunk(
                    chunk_text=split_chunk_text,
                    chunk_id=f"{chunk_id_prefix}_{counter}",
                    professor=professor,
                    professor_id=professor_id,
                    source_file=source_file,
                    review=review,
                )
            )
            counter += 1

        if end >= len(review_text):
            break
        start += step

    return chunks


def build_chunks(documents_dir: str | Path = DOCUMENTS_DIR) -> list[dict[str, str]]:
    """Read professor documents and return chunks in memory."""
    documents_path = Path(documents_dir)
    if not documents_path.exists():
        raise FileNotFoundError(f"Documents directory not found: {documents_path}")

    chunks = []
    for path in sorted(documents_path.glob("*.txt")):
        text = path.read_text(encoding="utf-8")
        blocks = [block.strip() for block in BLOCK_SPLIT_RE.split(text.strip()) if block.strip()]
        if not blocks:
            continue

        source_file = path.name
        professor_id = _professor_id_from_filename(source_file)
        professor = _parse_professor_name(blocks[0], fallback=path.stem)
        chunk_id_prefix = _source_prefix(source_file)
        next_chunk_number = 0

        for block in blocks:
            if not block.startswith("Course:"):
                continue

            review_chunks = chunk_review_block(
                block,
                professor=professor,
                professor_id=professor_id,
                source_file=source_file,
                chunk_id_prefix=chunk_id_prefix,
                first_chunk_number=next_chunk_number,
            )
            chunks.extend(review_chunks)
            next_chunk_number += len(review_chunks)

    return chunks


def save_chunks_json(
    chunks: list[dict[str, str]], output_path: str | Path = OUTPUT_FILE
) -> None:
    """Optional debugging helper; the main pipeline does not depend on JSON."""
    Path(output_path).write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


if __name__ == "__main__":
    built_chunks = build_chunks()
    print(f"Built {len(built_chunks)} chunks from {DOCUMENTS_DIR}/")
