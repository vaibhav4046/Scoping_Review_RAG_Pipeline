"""
Unified LLM client supporting Ollama (local), Google Gemini, and Groq.
All providers return structured JSON via system prompts.
"""

import json
import logging
from typing import Any, Optional

import google.generativeai as genai
from groq import Groq
import ollama as ollama_client
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMClient:
    """Unified interface for multiple LLM providers."""

    def __init__(self):
        # Initialize Gemini
        if settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)

        # Initialize Groq
        self._groq_client = None
        if settings.groq_api_key:
            self._groq_client = Groq(api_key=settings.groq_api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        provider: str,
        model: str,
        system_prompt: str = "",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """Generate text from any configured LLM provider."""
        logger.info(f"LLM call: provider={provider}, model={model}")

        if provider == "gemini":
            return await self._gemini_generate(
                prompt, model, system_prompt, temperature, max_tokens, json_mode
            )
        elif provider == "groq":
            return await self._groq_generate(
                prompt, model, system_prompt, temperature, max_tokens, json_mode
            )
        elif provider == "ollama":
            return await self._ollama_generate(
                prompt, model, system_prompt, temperature, max_tokens, json_mode
            )
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    async def generate_json(
        self,
        prompt: str,
        provider: str,
        model: str,
        system_prompt: str = "",
        temperature: float = 0.1,
    ) -> dict:
        """Generate and parse JSON from LLM."""
        response = await self.generate(
            prompt=prompt,
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
            json_mode=True,
        )
        # Parse JSON, handling markdown code blocks
        text = response.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return json.loads(text.strip())

    async def _gemini_generate(
        self, prompt: str, model: str, system_prompt: str,
        temperature: float, max_tokens: int, json_mode: bool,
    ) -> str:
        gen_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if json_mode:
            gen_config.response_mime_type = "application/json"

        gemini_model = genai.GenerativeModel(
            model_name=model,
            system_instruction=system_prompt if system_prompt else None,
            generation_config=gen_config,
        )
        response = gemini_model.generate_content(prompt)
        return response.text

    async def _groq_generate(
        self, prompt: str, model: str, system_prompt: str,
        temperature: float, max_tokens: int, json_mode: bool,
    ) -> str:
        if not self._groq_client:
            raise RuntimeError("Groq API key not configured")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self._groq_client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    async def _ollama_generate(
        self, prompt: str, model: str, system_prompt: str,
        temperature: float, max_tokens: int, json_mode: bool,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = ollama_client.chat(
            model=model,
            messages=messages,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            format="json" if json_mode else "",
        )
        return response["message"]["content"]

    async def primary_generate(
        self, prompt: str, system_prompt: str = "", json_mode: bool = False,
    ) -> str:
        """Use the configured primary LLM."""
        return await self.generate(
            prompt=prompt,
            provider=settings.primary_llm_provider,
            model=settings.primary_llm_model,
            system_prompt=system_prompt,
            json_mode=json_mode,
        )

    async def primary_generate_json(
        self, prompt: str, system_prompt: str = "",
    ) -> dict:
        """Use the configured primary LLM with JSON output."""
        return await self.generate_json(
            prompt=prompt,
            provider=settings.primary_llm_provider,
            model=settings.primary_llm_model,
            system_prompt=system_prompt,
        )

    async def validator_generate_json(
        self, prompt: str, system_prompt: str = "",
    ) -> dict:
        """Use the configured validator LLM with JSON output."""
        return await self.generate_json(
            prompt=prompt,
            provider=settings.validator_llm_provider,
            model=settings.validator_llm_model,
            system_prompt=system_prompt,
        )


# Singleton
llm_client = LLMClient()
