"""Small structured-output wrapper around a local Ollama model.

The model is only ever asked to *interpret* text or *choose* from options that
came from a real source. It is never asked for numbers.
"""
from __future__ import annotations

import json
import logging
import os
from typing import TypeVar

import requests
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("SHORTS_MODEL", "qwen3:8b")

log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


def ask(schema: type[T], prompt: str, *, max_tokens: int = 800, attempts: int = 3) -> T:
    """Return an instance of `schema` produced by the model, retrying on invalid output."""
    errors: list[str] = []
    for attempt in range(attempts):
        full_prompt = "/no_think\n" + prompt
        if errors:
            full_prompt += "\n\nYour previous answer was invalid: " + errors[-1][:400] + "\nReturn valid JSON for the schema."
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": MODEL,
                    "prompt": full_prompt,
                    "format": schema.model_json_schema(),
                    "stream": False,
                    "think": False,
                    "options": {
                        "temperature": 0,
                        "num_ctx": 8192,
                        "num_predict": max_tokens,
                        "seed": int(os.getenv("SHORTS_SEED", "42")),
                    },
                },
                timeout=(10, 900),
            )
            response.raise_for_status()
            return schema.model_validate_json(response.json()["response"])
        except (requests.RequestException, ValidationError, KeyError, json.JSONDecodeError) as exc:
            log.warning("LLM attempt %d failed: %s", attempt + 1, exc)
            errors.append(str(exc))
    raise LLMError(f"Model could not produce a valid {schema.__name__}: {errors[-1] if errors else 'unknown'}")
