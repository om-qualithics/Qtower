from apps.api.modules.ai_gateway.providers.base import ProviderResponse

MOCK_MODEL = "mock-echo-1"


class MockProvider:
    """No external calls - always available, used by default so the rest
    of the app can be built and tested without an Anthropic key."""

    def complete(self, prompt: str, system: str | None = None) -> ProviderResponse:
        content = f"[mock response] {prompt[:200]}"
        # Rough length-based estimate, not real usage data - clearly fake,
        # never meant to resemble a real token count.
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(content) // 4)
        return ProviderResponse(
            content=content,
            model=MOCK_MODEL,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=0.0,
        )
