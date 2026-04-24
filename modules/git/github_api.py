from __future__ import annotations
import httpx

from nexus.core.logger import get

log = get("git.github_api")


async def list_repos(token: str) -> list[dict]:
    """Fetch all repos accessible with the given PAT, sorted by last push."""
    log.info("Fetching GitHub repo list")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repos: list[dict] = []
    page = 1
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            while True:
                r = await client.get(
                    "https://api.github.com/user/repos",
                    headers=headers,
                    params={"per_page": 100, "page": page, "sort": "pushed"},
                )
                r.raise_for_status()
                batch = r.json()
                if not batch:
                    break
                repos.extend(batch)
                log.debug("Fetched page %d (%d repos so far)", page, len(repos))
                page += 1
                if len(batch) < 100:
                    break
    except httpx.HTTPStatusError as exc:
        log.error("GitHub API HTTP error: %s %s", exc.response.status_code, exc.response.text[:200])
        raise
    except httpx.RequestError as exc:
        log.error("GitHub API request failed: %s", exc)
        raise
    except Exception:
        log.exception("Unexpected error fetching GitHub repos")
        raise

    log.info("Fetched %d repos from GitHub", len(repos))
    return [
        {
            "name":        r["name"],
            "full_name":   r["full_name"],
            "clone_url":   r["clone_url"],
            "ssh_url":     r["ssh_url"],
            "private":     r["private"],
            "description": r.get("description") or "",
        }
        for r in repos
    ]


async def verify_token(token: str) -> tuple[bool, str]:
    """Returns (ok, username_or_error)."""
    log.debug("Verifying GitHub token")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
        if r.status_code == 200:
            username = r.json().get("login", "")
            log.info("GitHub token valid for user: %s", username)
            return True, username
        log.warning("GitHub token verification failed: HTTP %s", r.status_code)
        return False, f"HTTP {r.status_code}"
    except Exception as exc:
        log.error("GitHub token verification error: %s", exc)
        return False, str(exc)
