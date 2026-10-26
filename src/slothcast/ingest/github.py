"""GitHub commit activity -> daily counts.

Commits are weak evidence. A commit does not prove you did the planned task, and no commit
does not prove you procrastinated. They are used (a) as a feature (yesterday's commits) and
(b) only to *infer* labels for days you forgot to check in, always tagged `inferred`.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from .. import config

API = "https://api.github.com"


def commits_to_daily(commits: list[dict], tz: str | None = None) -> pd.DataFrame:
    """Pure function: GitHub commit objects -> DataFrame[date, commits] in local days."""
    tz = tz or config.TZ
    stamps = []
    for c in commits:
        info = c.get("commit", {})
        ts = (info.get("author") or {}).get("date") or (info.get("committer") or {}).get("date")
        if ts:
            stamps.append(ts)
    if not stamps:
        return pd.DataFrame(columns=["date", "commits"])
    days = pd.to_datetime(pd.Series(stamps), utc=True).dt.tz_convert(tz).dt.tz_localize(None).dt.normalize()
    out = days.value_counts().rename_axis("date").reset_index(name="commits")
    return out.sort_values("date").reset_index(drop=True)


def _get(session: requests.Session, url: str, params: dict | None = None):
    resp = session.get(url, params=params, timeout=30)
    if resp.status_code == 403 and resp.headers.get("X-RateLimit-Remaining") == "0":
        raise RuntimeError("GitHub rate limit reached; set GITHUB_TOKEN and retry later")
    if resp.status_code == 409:  # empty repository
        return []
    resp.raise_for_status()
    return resp.json()


def fetch_commits(
    username: str,
    token: str | None = None,
    since: str | None = None,
    max_repos: int = 100,
    tz: str | None = None,
) -> pd.DataFrame:
    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github+json"
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
        repos_url = f"{API}/user/repos"
        repo_params = {"per_page": 100, "sort": "pushed", "affiliation": "owner,collaborator"}
    else:
        repos_url = f"{API}/users/{username}/repos"
        repo_params = {"per_page": 100, "sort": "pushed"}
    repos = _get(session, repos_url, repo_params)[:max_repos]

    all_commits: list[dict] = []
    for repo in repos:
        for page in range(1, 11):
            params = {"author": username, "per_page": 100, "page": page}
            if since:
                params["since"] = pd.Timestamp(since).strftime("%Y-%m-%dT00:00:00Z")
            batch = _get(session, f"{API}/repos/{repo['full_name']}/commits", params)
            all_commits.extend(batch)
            if len(batch) < 100:
                break
    return commits_to_daily(all_commits, tz)


def load_commits(path: str | Path | None = None) -> pd.DataFrame | None:
    path = Path(path or config.COMMITS_PATH)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if df.empty:
        return None
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["commits"] = pd.to_numeric(df["commits"], errors="coerce").fillna(0)
    return df[["date", "commits"]]


def update_commits_csv(
    username: str,
    token: str | None = None,
    since: str | None = None,
    path: str | Path | None = None,
    tz: str | None = None,
) -> pd.DataFrame:
    """Fetch commits since `since` and merge into the local CSV (fetched range replaces old)."""
    path = Path(path or config.COMMITS_PATH)
    since = since or (pd.Timestamp.today().normalize() - pd.Timedelta(days=120)).strftime("%Y-%m-%d")
    fresh = fetch_commits(username, token, since, tz=tz)
    old = load_commits(path)
    since_ts = pd.Timestamp(since).normalize()
    keep_old = old[old["date"] < since_ts] if old is not None else None
    frames = [f for f in (keep_old, fresh) if f is not None and not f.empty]
    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "commits"])
    path.parent.mkdir(parents=True, exist_ok=True)
    out = out.sort_values("date")
    out.assign(date=pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")).to_csv(path, index=False)
    return out
