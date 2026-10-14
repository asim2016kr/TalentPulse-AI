"""Small provider boundary; both providers return the same validated contract."""
import json
import math
import os
import re
import time
from contextlib import contextmanager

import requests

try:
    from .classification_contract import Classification
except ImportError:
    from classification_contract import Classification


class ProviderError(RuntimeError):
    """Safe to report: never includes raw provider bodies, headers or credentials."""


class GeminiPredictor:
    provider = "gemini"

    def __init__(self, api_key, model, min_interval=7.0, session=None):
        if not api_key or api_key.startswith("YOUR_"):
            raise ValueError("Configure GEMINI_API_KEY in the local .env")
        if not re.fullmatch(r"[a-zA-Z0-9._-]+", model):
            raise ValueError("Invalid Gemini model identifier")
        if not math.isfinite(min_interval) or min_interval < 0:
            raise ValueError("GEMINI_MIN_INTERVAL must be finite and nonnegative")
        self.model = model
        self.interval = min_interval
        self.session = session or requests.Session()
        self.headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        self.last_request = None
        self.last_metadata = {}

    def __call__(self, row):
        try:
            from .ai_classifier import PROMPT
        except ImportError:
            from ai_classifier import PROMPT
        payload = {
            "systemInstruction": {"parts": [{"text": PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(
                {"job_title": row["job_title"], "tags": row["tags"]}, ensure_ascii=False)}]}],
            "generationConfig": {"responseMimeType": "application/json",
                                 "responseJsonSchema": Classification.model_json_schema(),
                                 "temperature": 0, "maxOutputTokens": 2048},
        }
        return self.generate(payload, Classification)

    def generate(self, payload, output_schema):
        """Reuse the validated Gemini transport for another bounded structured contract."""
        for attempt in range(3):
            if self.last_request is not None:
                time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                response = self.session.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                    headers=self.headers, json=payload, timeout=(10, 45), allow_redirects=False)
            except requests.RequestException:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise ProviderError("Gemini connection failed after bounded retries") from None
            try:
                data = response.json()
            except ValueError:
                raise ProviderError("Gemini returned a non-JSON HTTP response") from None
            if response.status_code != 200:
                error = data.get("error", {})
                details = error.get("details", [])
                violations = [v for d in details for v in d.get("violations", [])]
                daily_or_zero = any("perday" in str(v.get("quotaId", "")).lower()
                                    or str(v.get("quotaValue", "")) == "0" for v in violations)
                retry_delay = 15 * (attempt + 1)
                for detail in details:
                    delay = str(detail.get("retryDelay", ""))
                    if re.fullmatch(r"\d+(?:\.\d+)?s", delay):
                        retry_delay = max(retry_delay, float(delay[:-1]) + 1)
                if response.status_code in (429, 500, 502, 503, 504) and attempt < 2 and not daily_or_zero and retry_delay <= 60:
                    time.sleep(retry_delay)
                    continue
                reason = "daily/zero quota" if daily_or_zero else "provider rejection"
                raise ProviderError(f"Gemini HTTP {response.status_code}: {reason}")
            if data.get("promptFeedback", {}).get("blockReason"):
                raise ProviderError("Gemini blocked the input")
            candidates = data.get("candidates", [])
            if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
                raise ProviderError("Gemini refused, truncated or omitted its classification")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
            if not text:
                raise ProviderError("Gemini returned no classification text")
            result = output_schema.model_validate_json(text)
            self.last_metadata = {"model_version": data.get("modelVersion"), "usage": data.get("usageMetadata", {})}
            return result

    def close(self):
        self.session.close()


@contextmanager
def configured_predictor(provider=None, model=None):
    provider = (provider or os.getenv("AI_PROVIDER") or ("gemini" if os.getenv("GEMINI_API_KEY") else "openai")).lower()
    if provider == "gemini":
        model = model or os.getenv("GEMINI_MODEL") or "gemini-3.1-flash-lite"
        predictor = GeminiPredictor(os.getenv("GEMINI_API_KEY"), model, float(os.getenv("GEMINI_MIN_INTERVAL", "7")))
        try:
            yield provider, model, predictor
        finally:
            predictor.close()
    elif provider == "openai":
        from openai import OpenAI
        try:
            from .ai_classifier import request_classification
        except ImportError:
            from ai_classifier import request_classification
        model = model or os.getenv("OPENAI_MODEL")
        if not model or not os.getenv("OPENAI_API_KEY"):
            raise ValueError("Configure OPENAI_MODEL and OPENAI_API_KEY")
        with OpenAI(timeout=45, max_retries=2) as client:
            yield provider, model, lambda row: request_classification(client, model, row)
    else:
        raise ValueError("AI_PROVIDER must be gemini or openai")
