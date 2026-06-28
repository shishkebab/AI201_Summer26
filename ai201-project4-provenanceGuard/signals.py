import json
import os
import re
from typing import Any

from dotenv import load_dotenv


GROQ_SIGNAL_NAME = "groq_llm_classifier"
STYLOMETRIC_SIGNAL_NAME = "stylometric_heuristics"


def _base_signal(
    name: str,
    status: str,
    ai_likelihood: float,
    quality: float,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "ai_likelihood": _clamp(ai_likelihood),
        "quality": _clamp(quality),
        "evidence": evidence,
    }


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _parse_json_response(content: str) -> dict[str, Any]:
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError("Groq response was not a JSON object")
    return parsed


def run_groq_llm_classifier(text: str) -> dict[str, Any]:
    """Return the first detection signal as an ai_likelihood score from 0.0 to 1.0."""
    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    if not api_key:
        return _base_signal(
            name=GROQ_SIGNAL_NAME,
            status="failed",
            ai_likelihood=0.5,
            quality=0.0,
            evidence={
                "rationale": "Groq classifier did not run because GROQ_API_KEY is not configured.",
                "uncertainty_notes": "Without the LLM signal, the system should treat attribution as uncertain.",
            },
        )

    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an attribution analysis component. Return only JSON with "
                        "ai_likelihood, rationale, and uncertainty_notes. ai_likelihood must be "
                        "a number from 0.0 to 1.0, where 0.0 means strongly human-likely and "
                        "1.0 means strongly AI-likely. Do not claim proof of authorship."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Analyze this text for AI-like versus human-like writing patterns. "
                        "Consider voice, specificity, flow, transitions, generic phrasing, "
                        "topic handling, and whether the writing feels personally situated.\n\n"
                        f"Text:\n{text}"
                    ),
                },
            ],
        )

        content = completion.choices[0].message.content or "{}"
        parsed = _parse_json_response(content)
        ai_likelihood = parsed.get("ai_likelihood")
        if ai_likelihood is None:
            raise ValueError("Groq response did not include ai_likelihood")

        return _base_signal(
            name=GROQ_SIGNAL_NAME,
            status="completed",
            ai_likelihood=float(ai_likelihood),
            quality=0.9,
            evidence={
                "rationale": str(parsed.get("rationale", "")),
                "uncertainty_notes": str(parsed.get("uncertainty_notes", "")),
            },
        )
    except Exception as exc:
        return _base_signal(
            name=GROQ_SIGNAL_NAME,
            status="failed",
            ai_likelihood=0.5,
            quality=0.0,
            evidence={
                "rationale": "Groq classifier failed to produce a usable structured response.",
                "uncertainty_notes": f"Signal failed with {type(exc).__name__}.",
            },
        )


def _words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text.lower())


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"[.!?]+", text) if sentence.strip()]


def _population_variance(values: list[int]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _repeated_bigram_ratio(words: list[str]) -> float:
    if len(words) < 2:
        return 0.0

    bigrams = list(zip(words, words[1:]))
    unique_bigrams = set(bigrams)
    repeated_count = len(bigrams) - len(unique_bigrams)
    return repeated_count / len(bigrams)


def _punctuation_density(text: str) -> float:
    non_space_chars = [char for char in text if not char.isspace()]
    if not non_space_chars:
        return 0.0
    punctuation_chars = [char for char in non_space_chars if re.match(r"[^\w\s]", char)]
    return len(punctuation_chars) / len(non_space_chars)


def run_stylometric_heuristics(text: str) -> dict[str, Any]:
    """Return a structural ai_likelihood score using local text statistics."""
    words = _words(text)
    sentences = _sentences(text)
    sentence_lengths = [_words(sentence) for sentence in sentences]
    sentence_word_counts = [len(sentence_words) for sentence_words in sentence_lengths if sentence_words]

    word_count = len(words)
    sentence_count = len(sentence_word_counts)
    average_sentence_length = sum(sentence_word_counts) / sentence_count if sentence_count else 0.0
    sentence_length_variance = _population_variance(sentence_word_counts)
    type_token_ratio = len(set(words)) / word_count if word_count else 0.0
    punctuation_density = _punctuation_density(text)
    repeated_bigram_ratio = _repeated_bigram_ratio(words)

    uniform_sentence_score = _clamp((25 - sentence_length_variance) / 25)
    low_vocab_score = _clamp((0.60 - type_token_ratio) / 0.30)
    regular_punctuation_score = 1 - _clamp(abs(punctuation_density - 0.045) / 0.045)
    repetition_score = _clamp(repeated_bigram_ratio / 0.08)

    ai_likelihood = (
        0.35 * uniform_sentence_score
        + 0.25 * low_vocab_score
        + 0.20 * regular_punctuation_score
        + 0.20 * repetition_score
    )

    quality = 0.85
    if word_count < 80:
        quality -= 0.25
    if sentence_count < 4:
        quality -= 0.25

    return _base_signal(
        name=STYLOMETRIC_SIGNAL_NAME,
        status="completed",
        ai_likelihood=ai_likelihood,
        quality=quality,
        evidence={
            "word_count": word_count,
            "sentence_count": sentence_count,
            "average_sentence_length": round(average_sentence_length, 3),
            "sentence_length_variance": round(sentence_length_variance, 3),
            "type_token_ratio": round(type_token_ratio, 3),
            "punctuation_density": round(punctuation_density, 3),
            "repeated_bigram_ratio": round(repeated_bigram_ratio, 3),
            "subscores": {
                "uniform_sentence_score": round(uniform_sentence_score, 3),
                "low_vocab_score": round(low_vocab_score, 3),
                "regular_punctuation_score": round(regular_punctuation_score, 3),
                "repetition_score": round(repetition_score, 3),
            },
        },
    )
