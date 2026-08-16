from dataclasses import dataclass
from typing import Protocol


@dataclass
class ProviderResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class Provider(Protocol):
    """Every provider (mock, Claude, ...) implements this one method.
    Feature code never talks to a Provider directly - only ai_gateway's
    service.complete() resolves and calls one (handoff §2.2)."""

    def complete(self, prompt: str, system: str | None = None) -> ProviderResponse: ...
