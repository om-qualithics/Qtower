from dataclasses import dataclass


@dataclass
class GatewayResponse:
    content: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
