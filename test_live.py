# -*- coding: utf-8 -*-
"""
test_live.py — Real Gemini API calls traced with the llmobs SDK.

Setup:
  1. pip install -e sdk/
  2. pip install google-genai python-dotenv
  3. Copy .env.example to .env and fill in GEMINI_API_KEY + LLMOBS_COLLECTOR_URL
  4. Start the API:  cd api && uvicorn main:app --reload
  5. Run:  python test_live.py
"""

import io
import os
import sys
import time

# Fix Windows terminal encoding for Unicode output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

from dotenv import load_dotenv

load_dotenv()

from google import genai as google_genai
from google.genai import types as genai_types

from llmobs import trace, span

# ---------------------------------------------------------------------------
# Configure Gemini
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example -> .env and fill it in.")

_client = google_genai.Client(api_key=GEMINI_API_KEY)
MODEL = "gemini-flash-latest"

# ---------------------------------------------------------------------------
# Traced functions — return the full response object so the SDK can extract
# token counts from response.usage_metadata automatically.
# ---------------------------------------------------------------------------

@trace(model=MODEL, tags={"env": "dev", "feature": "summarizer"})
def summarize(text: str):
    """Summarize a passage in two sentences."""
    return _client.models.generate_content(
        model=MODEL,
        contents=f"Summarize the following text in exactly 2 sentences:\n\n{text}",
    )


@trace(model=MODEL, tags={"env": "dev", "feature": "classifier"})
def classify_sentiment(text: str):
    """Classify sentiment as positive / negative / neutral."""
    return _client.models.generate_content(
        model=MODEL,
        contents=(
            "Classify the sentiment of this text as positive, negative, or neutral. "
            f"Reply with one word only.\n\nText: {text}"
        ),
    )


@trace(model=MODEL, tags={"env": "prod", "feature": "qa"})
def answer_question(context: str, question: str):
    """Answer a question based on context."""
    return _client.models.generate_content(
        model=MODEL,
        contents=f"Context: {context}\n\nQuestion: {question}\n\nAnswer concisely:",
    )


@trace(model=MODEL, tags={"env": "staging", "feature": "rewriter"})
def rewrite_formal(text: str):
    """Rewrite text in a formal, professional tone."""
    return _client.models.generate_content(
        model=MODEL,
        contents=f"Rewrite the following text in a formal, professional tone:\n\n{text}",
    )


@trace(model=MODEL, tags={"env": "prod", "feature": "chat"})
def chat_respond(message: str):
    """General chat response."""
    return _client.models.generate_content(
        model=MODEL,
        contents=message,
    )


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

SUMMARIES = [
    (
        "Machine learning is a branch of artificial intelligence that enables systems to learn "
        "from data and improve their performance over time without being explicitly programmed. "
        "It uses statistical techniques to give computers the ability to learn from experience."
    ),
    (
        "The Python programming language was created by Guido van Rossum and first released in 1991. "
        "It emphasises code readability and uses significant whitespace. Python supports multiple "
        "programming paradigms including procedural, object-oriented, and functional programming."
    ),
]

SENTIMENTS = [
    "I absolutely love this product! It works perfectly and exceeded all my expectations.",
    "This is the worst experience I've ever had. Completely broken and useless.",
    "The package arrived on Tuesday. It was in a brown box.",
]

QA_PAIRS = [
    (
        "FastAPI is a modern, fast web framework for building APIs with Python 3.7+ based on "
        "standard Python type hints. It is built on top of Starlette and Pydantic.",
        "What is FastAPI built on top of?",
    ),
    (
        "Observability in software engineering refers to the ability to infer the internal state "
        "of a system by examining its outputs such as logs, metrics, and traces.",
        "What are the three pillars of observability?",
    ),
]

REWRITES = [
    "hey can u fix the bug asap its super urgent lol",
    "just wanted to check in about the meeting tomorrow, r we still doing it?",
]

CHAT_MESSAGES = [
    "What is the difference between precision and recall in machine learning?",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_call(fn, *args, delay: float = 5.0, **kwargs):
    """Call fn, print result preview, wait to respect rate limits."""
    try:
        result = fn(*args, **kwargs)
        text = result.text[:80].strip().replace("\n", " ") if hasattr(result, "text") else str(result)[:80]
        tokens = getattr(getattr(result, "usage_metadata", None), "total_token_count", "?")
        print(f"  [OK] {fn.__name__} | {tokens} tokens | {text!r}...")
    except Exception as exc:
        print(f"  [ERROR] {fn.__name__} raised {type(exc).__name__}: {str(exc)[:120]}")
    time.sleep(delay)


def run_span_demo():
    print("\n[span demo - context manager]")
    prompt = "What is observability in software engineering? Answer in one short paragraph."
    with span(model=MODEL, tags={"env": "dev", "feature": "chat"}) as s:
        s.set_input(prompt)
        response = _client.models.generate_content(model=MODEL, contents=prompt)
        s.set_output(response)
    text = response.text[:80].strip().replace("\n", " ")
    tokens = getattr(response.usage_metadata, "total_token_count", "?")
    print(f"  [OK] span | {tokens} tokens | {text!r}...")
    time.sleep(5.0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    collector_url = os.getenv("LLMOBS_COLLECTOR_URL", "http://localhost:8000")
    total_calls = len(SUMMARIES) + len(SENTIMENTS) + len(QA_PAIRS) + len(REWRITES) + len(CHAT_MESSAGES) + 1
    print(f"Watch your LLM - Live Test")
    print(f"Collector: {collector_url}")
    print(f"Model:     {MODEL}")
    print(f"Calls:     {total_calls}\n")

    print("[summarizer]")
    for text in SUMMARIES:
        run_call(summarize, text)

    print("\n[sentiment classifier]")
    for text in SENTIMENTS:
        run_call(classify_sentiment, text)

    print("\n[Q&A]")
    for context, question in QA_PAIRS:
        run_call(answer_question, context, question)

    print("\n[rewriter]")
    for text in REWRITES:
        run_call(rewrite_formal, text)

    print("\n[chat]")
    for message in CHAT_MESSAGES:
        run_call(chat_respond, message)

    run_span_demo()

    # Give the background sender thread a moment to flush
    time.sleep(3)
    print(f"\nDone! {total_calls} traces sent.")
    print(f"Open http://localhost:5173/app to explore.\n")


if __name__ == "__main__":
    main()
