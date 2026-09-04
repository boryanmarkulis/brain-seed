#!/usr/bin/env python3
"""
brain_config.py -- the one place the Brain learns who it belongs to.

Every script and every LLM prompt in this repo is written for "the owner".
Nothing is hardcoded to a person. The values come from `brain.config.json`
at the repo root, which `/onboard` writes during the interview.

    from brain_config import cfg
    cfg.owner        # "Ada Lovelace"
    cfg.mission      # "Make computation useful to everyone"
    cfg.render(TMPL) # fills {owner} / {mission} / {work} / {voice} in a prompt

If the config file is missing or half-filled, sensible neutral defaults are
used so a fresh clone still runs instead of crashing.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "brain.config.json"

DEFAULTS: dict = {
    "owner": "the owner",
    "mission": "not set yet -- run /onboard",
    "work": "not set yet -- run /onboard",
    "voice": "direct, casual, plain words, no corporate tone",
    "timezone": "UTC",
    "domains": [],
    "wiki_scope": "everything the owner has learned or done",
    "local_model": "qwen3-30b-a3b",
    "embed_model": "qwen3-embed-4b",
    "compile_model": "claude-sonnet-4-6",
    "extract_model": "claude-haiku-4-5-20251001",
    "compile_provider": "auto",
    "git_branch": "main",
    "health_checks": [
        {"label": "push to GitHub", "ok": "PUSH OK", "fail": "PUSH FAILED"}
    ],
}


@dataclass
class BrainConfig:
    data: dict = field(default_factory=dict)

    def __getattr__(self, name: str):
        # dataclass field lookup happens first; this only sees config keys
        if name in self.data:
            return self.data[name]
        if name in DEFAULTS:
            return DEFAULTS[name]
        raise AttributeError(name)

    def get(self, name: str, default=None):
        return self.data.get(name, DEFAULTS.get(name, default))

    @property
    def is_configured(self) -> bool:
        return bool(self.data.get("owner")) and self.data.get("owner") != DEFAULTS["owner"]

    @property
    def domain_list(self) -> str:
        d = self.get("domains") or []
        return ", ".join(d) if d else "any subject the owner works on"

    def render(self, template: str) -> str:
        """Fill {owner}, {mission}, {work}, {voice}, {domains}, {wiki_scope}.

        Uses a targeted regex rather than str.format so that literal braces in
        prompts (JSON examples, GBNF snippets) survive untouched.
        """
        keys = {
            "owner": self.owner,
            "mission": self.mission,
            "work": self.work,
            "voice": self.voice,
            "domains": self.domain_list,
            "wiki_scope": self.wiki_scope,
            "timezone": self.timezone,
        }
        return re.sub(
            r"\{(" + "|".join(keys) + r")\}",
            lambda m: str(keys[m.group(1)]),
            template,
        )


def load(path: Path | None = None) -> BrainConfig:
    p = path or CONFIG_PATH
    data = dict(DEFAULTS)
    if p.exists():
        try:
            data.update(json.loads(p.read_text()))
        except Exception:
            pass
    # environment always wins, so a one-off run can override without editing
    for key in DEFAULTS:
        env = os.environ.get("BRAIN_" + key.upper())
        if env:
            data[key] = env
    return BrainConfig(data)


cfg = load()


def memory_dir() -> Path:
    """Where the agent's short-term feedback memories live.

    Claude Code namespaces these by an escaped absolute project path. Codex,
    Cursor and the rest do not, so fall back to a repo-local folder that every
    tool can read.
    """
    override = os.environ.get("BRAIN_MEMORY_DIR")
    if override:
        return Path(override).expanduser()

    slug = str(REPO_ROOT).replace("/", "-")
    claude_dir = Path.home() / ".claude" / "projects" / slug / "memory"
    if claude_dir.exists():
        return claude_dir
    return REPO_ROOT / ".claude" / "memory"


if __name__ == "__main__":
    print(json.dumps(cfg.data, indent=2))
    print("memory_dir:", memory_dir())
    print("configured:", cfg.is_configured)
