"""Ollama chat backend.

Keeps the surface tiny: one POST to /api/chat. Uses httpx so we don't pull
in langchain. Caller is responsible for retries beyond what's here.
"""
from __future__ import annotations

import asyncio

import httpx


class OllamaLLM:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0,
                 max_retries: int = 2, retry_delay: float = 1.5):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    async def complete(self, prompt: str, system: str | None = None) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0},
        }
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    r = await client.post(f"{self.base_url}/api/chat", json=payload)
                    r.raise_for_status()
                    data = r.json()
                return (data.get("message") or {}).get("content", "")
            except Exception as e:
                last_err = e
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (2 ** attempt))
        raise RuntimeError(f"Ollama request failed after retries: {last_err}")
