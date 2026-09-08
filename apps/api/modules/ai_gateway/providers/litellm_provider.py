import logging
import time

import litellm

from apps.api.core.settings import settings
from apps.api.modules.ai_gateway.providers.base import ProviderResponse

logger = logging.getLogger(__name__)

# Was 1024 - real M10 tool-assessment traffic showed the model exceeding
# its "under 300 words" rationale instruction and hitting that cap exactly
# (completion_tokens=1024 in llm_usage_log), truncating the JSON mid-string
# and forcing a fail-safe "failed" assessment with no visible evaluation.
# max_tokens is a ceiling, not a reservation - raising it only costs money
# if the model actually generates more, so this is free headroom.
MAX_TOKENS = 4096
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 1.0


class LiteLlmProvider:
    """Vendor-agnostic real provider. Delegates to LiteLLM
    (https://github.com/BerriAI/litellm), which exposes one completion()
    call across Anthropic/OpenAI/Google/Azure/Bedrock/etc - the vendor is
    selected entirely by settings.ai_model's prefix (e.g.
    "anthropic/claude-sonnet-5" vs "openai/gpt-4o"), so switching providers
    is a config change, not a new provider class. LiteLLM also normalizes
    token usage and cost across vendors, so no hand-maintained pricing
    table is needed here."""

    def __init__(self) -> None:
        self._model = settings.ai_model

    def complete(self, prompt: str, system: str | None = None) -> ProviderResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = self._call_with_retry(messages)

        content = response.choices[0].message.content or ""
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        try:
            cost_usd = litellm.completion_cost(completion_response=response)
        except Exception:
            # LiteLLM's pricing table doesn't cover every model - cost
            # tracking is best-effort, missing it shouldn't fail the call.
            cost_usd = 0.0

        return ProviderResponse(
            content=content,
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
        )

    def _call_with_retry(self, messages: list[dict]):
        # The real ceiling on throughput is the vendor's own rate limits,
        # not anything in our code - this is cheap insurance against
        # transient 429s, not a substitute for a queue/backpressure story.
        for attempt in range(MAX_RETRIES):
            try:
                return litellm.completion(
                    model=self._model,
                    api_key=settings.ai_api_key,
                    max_tokens=MAX_TOKENS,
                    messages=messages,
                )
            except litellm.RateLimitError:
                if attempt == MAX_RETRIES - 1:
                    raise
                delay = BASE_BACKOFF_SECONDS * (2**attempt)
                logger.warning("Provider rate-limited, retrying in %.1fs", delay)
                time.sleep(delay)
