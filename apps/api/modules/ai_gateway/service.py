from apps.api.core.db import org_scoped_session
from apps.api.core.settings import settings
from apps.api.modules.ai_gateway.models import LlmUsageLog
from apps.api.modules.ai_gateway.providers.base import Provider
from apps.api.modules.ai_gateway.schemas import GatewayResponse
from apps.api.modules.identity.models import Org


class AiGatewayConfigError(RuntimeError):
    pass


def _resolve_provider() -> tuple[str, Provider]:
    if settings.ai_provider == "mock":
        from apps.api.modules.ai_gateway.providers.mock import MockProvider

        return "mock", MockProvider()

    if settings.ai_provider == "live":
        if not settings.ai_api_key:
            raise AiGatewayConfigError(
                "AI_PROVIDER=live but AI_API_KEY is not set - refusing to "
                "silently fall back to the mock provider"
            )
        from apps.api.modules.ai_gateway.providers.litellm_provider import LiteLlmProvider

        # ai_model is "vendor/model", e.g. "anthropic/claude-sonnet-5" -
        # the vendor prefix is what we log as the provider.
        vendor = settings.ai_model.split("/", 1)[0]
        return vendor, LiteLlmProvider()

    raise AiGatewayConfigError(f"Unknown AI_PROVIDER: {settings.ai_provider!r}")


def complete(feature: str, org: Org, prompt: str, system: str | None = None) -> GatewayResponse:
    """The one function every feature module is allowed to call for an LLM
    completion (handoff §2.2) - no feature code talks to a Provider or an
    SDK directly.

    This is a plain blocking function, not something a FastAPI route
    handler should call inline: at real concurrency it would exhaust the
    sync thread pool. Any real feature path must invoke this from a Celery
    task (apps/api/core/celery_app.py), never synchronously from a route.
    """
    provider_name, provider = _resolve_provider()
    result = provider.complete(prompt, system=system)

    with org_scoped_session(str(org.id)) as db:
        db.add(
            LlmUsageLog(
                org_id=org.id,
                feature=feature,
                provider=provider_name,
                model=result.model,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                cost_usd=result.cost_usd,
            )
        )

    return GatewayResponse(
        content=result.content,
        provider=provider_name,
        model=result.model,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        cost_usd=result.cost_usd,
    )
