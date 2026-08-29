"""GitHub App auth + repo discovery for a self-owned, per-org App (see
plan: no shared vendor App, no callback URL). Plain httpx calls, matching
every other external HTTP call in this codebase (identity/service.py's
Jackson calls, ai_gateway's LiteLLM calls) - no new HTTP client
dependency."""

import time

import httpx
import jwt

GITHUB_API_BASE = "https://api.github.com"
_API_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


class GithubClientError(Exception):
    pass


def _app_jwt(app_id: str, private_key_pem: str) -> str:
    now = int(time.time())
    payload = {
        "iat": now - 60,  # allow for clock drift, GitHub's own documented recommendation
        "exp": now + 540,  # 9 minutes - under GitHub's 10-minute max
        "iss": app_id,
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def mint_installation_token(app_id: str, private_key_pem: str, installation_id: str) -> str:
    """Short-lived (1hr) token scoped to whatever repos this installation
    was granted - re-minted per use rather than cached, Phase 1 keeps
    this simple rather than adding a token cache."""
    try:
        app_token = _app_jwt(app_id, private_key_pem)
    except (jwt.PyJWTError, ValueError) as exc:
        raise GithubClientError(f"Could not sign a GitHub App JWT with the provided private key: {exc}") from exc

    resp = httpx.post(
        f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens",
        headers={**_API_HEADERS, "Authorization": f"Bearer {app_token}"},
        timeout=10,
    )
    if resp.status_code != 201:
        raise GithubClientError(f"GitHub rejected the App credentials (HTTP {resp.status_code}): {resp.text[:300]}")
    return resp.json()["token"]


def list_repositories(installation_token: str) -> list[dict]:
    """All repos this installation was granted, paginated."""
    repos: list[dict] = []
    page = 1
    while True:
        resp = httpx.get(
            f"{GITHUB_API_BASE}/installation/repositories",
            headers={**_API_HEADERS, "Authorization": f"Bearer {installation_token}"},
            params={"per_page": 100, "page": page},
            timeout=10,
        )
        if resp.status_code != 200:
            raise GithubClientError(f"Failed to list repositories (HTTP {resp.status_code}): {resp.text[:300]}")
        body = resp.json()
        repos.extend(body.get("repositories", []))
        if len(body.get("repositories", [])) < 100:
            break
        page += 1
    return repos


def clone_url_with_token(repo_full_name: str, installation_token: str) -> str:
    """x-access-token is GitHub's documented scheme for authenticating a
    git clone with an installation token (as opposed to a personal
    username/password)."""
    return f"https://x-access-token:{installation_token}@github.com/{repo_full_name}.git"
