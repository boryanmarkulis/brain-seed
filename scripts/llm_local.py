#!/usr/bin/env python3
"""
llm_local.py: shared llama.cpp client for the Brain's local pipelines.

Stage 1 (wiki_extract.py) and Stage 2 (wiki_consolidate.py) both talk to the
same local llama-server. This module owns the model registry, server lifecycle
and the completion call so neither stage keeps its own copy.

  from llm_local import MODELS, ensure_server, stop_server, complete, chatml

Everything here is local and free. Nothing in this module calls a paid API.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

MODELS_DIR = Path.home() / ".cache" / "llama-models"
HF_HUB = Path.home() / ".cache" / "huggingface" / "hub"
LLAMA_SERVER = "/opt/homebrew/bin/llama-server"
SERVER_LOG_DIR = Path.home() / "Library" / "Logs" / "brain"
DEFAULT_PORT = 8080

# think=True injects an empty <think></think> block after the assistant turn.
# On Qwen3 hybrid-reasoning models that is what switches reasoning off so a GBNF
# grammar applies from the very first token. The *-Instruct-2507 models are
# non-thinking by design and must NOT get the block.
MODELS: dict[str, dict] = {
    "qwen3-8b": {
        "file": "Qwen3-8B-Q4_K_M.gguf",
        "hf_glob": "models--unsloth--Qwen3-8B-GGUF/snapshots/*/Qwen3-8B-Q4_K_M.gguf",
        "ctx": 32768,
        "think": True,
        "note": "16GB-era default. Kept so old runs stay reproducible.",
    },
    "qwen3-30b-a3b": {
        "file": "Qwen3-30B-A3B-Instruct-2507-Q4_K_M.gguf",
        "ctx": 32768,
        "think": False,
        "bytes": 18_556_686_752,
        "note": "MoE, 3B active. Fast. Bench candidate.",
    },
    "qwen3-32b": {
        "file": "Qwen3-32B-Q4_K_M.gguf",
        "ctx": 32768,
        "think": True,
        "bytes": 19_762_150_048,
        "note": "Dense. Slower, stronger judgment. Bench candidate.",
    },
    # Embedding model, not a chat model. Serve it with
    # extra_args=["--embedding", "--pooling", "last"] on its own port and talk
    # to /v1/embeddings. Qwen3-Embedding pools on the last token, so the
    # pooling flag is not optional.
    "qwen3-embed-0.6b": {
        "file": "Qwen3-Embedding-0.6B-f16.gguf",
        "ctx": 8192,
        "think": False,
        "bytes": 1_197_629_632,
        "embedding": True,
        "dims": 1024,
        "note": "f16 not quantized: quantization costs more on embeddings than on generation.",
    },
}

# Exact expected byte counts, not a ratio. A 99.4%-written gguf passed a 97%
# ratio check once and llama-server died with "tensor 'blk.47.ffn_down_exps.
# weight' data is not within the file bounds", which reads like corruption
# rather than the truncated download it actually was. Exact or nothing.

DEFAULT_MODEL = "qwen3-30b-a3b"


class LocalModelError(RuntimeError):
    pass


def model_spec(name: str) -> dict:
    if name not in MODELS:
        raise LocalModelError(f"unknown model '{name}'. Known: {', '.join(MODELS)}")
    return MODELS[name]


def model_path(name: str) -> Path:
    """Resolve a registry name to a gguf on disk.

    Looks in ~/.cache/llama-models first, then falls back to the HuggingFace hub
    layout for models pulled before that directory existed.
    """
    spec = model_spec(name)
    found = None
    direct = MODELS_DIR / spec["file"]
    if direct.exists():
        found = direct
    elif spec.get("hf_glob"):
        hits = sorted(HF_HUB.glob(spec["hf_glob"]))
        if hits:
            found = hits[0]
    if found is None:
        raise LocalModelError(
            f"{spec['file']} not found. Looked in {MODELS_DIR} and the HuggingFace cache."
        )

    want = spec.get("bytes")
    if want:
        have = found.stat().st_size
        if have != want:
            short = "incomplete" if have < want else "unexpected"
            raise LocalModelError(
                f"{found.name} is {have:,} bytes, expected exactly {want:,} "
                f"({have / 1e9:.2f} vs {want / 1e9:.2f} GB). Download is {short}; "
                f"run: python3 scripts/fetch_model.py {name}"
            )
    return found


def available() -> dict[str, bool]:
    """Registry name -> is the gguf actually on disk."""
    out = {}
    for name in MODELS:
        try:
            model_path(name)
            out[name] = True
        except LocalModelError:
            out[name] = False
    return out


# --------------------------------------------------------------------------- #
# server lifecycle
# --------------------------------------------------------------------------- #

def server_url(port: int = DEFAULT_PORT) -> str:
    return f"http://127.0.0.1:{port}"


def server_up(port: int = DEFAULT_PORT, timeout: int = 3) -> bool:
    try:
        with urllib.request.urlopen(f"{server_url(port)}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def loaded_model(port: int = DEFAULT_PORT) -> str | None:
    """Path of the gguf the running server has loaded, or None."""
    try:
        with urllib.request.urlopen(f"{server_url(port)}/props", timeout=5) as r:
            props = json.loads(r.read())
    except Exception:
        return None
    return props.get("model_path") or props.get("default_generation_settings", {}).get("model")


def ensure_server(
    name: str = DEFAULT_MODEL,
    port: int = DEFAULT_PORT,
    ctx: int | None = None,
    wait: int = 300,
    log=print,
    extra_args: list[str] | None = None,
) -> bool:
    """Make sure a llama-server with THIS model is listening on `port`.

    Returns True if we started it (caller owns shutdown), False if we are
    reusing one that was already up.

    A server running a *different* model is stopped and replaced. Silently
    reusing the wrong model is the kind of thing that costs a whole overnight
    run, so it is worth the restart.
    """
    path = model_path(name)
    spec = model_spec(name)
    ctx = ctx or spec["ctx"]

    if server_up(port):
        current = loaded_model(port)
        if current and Path(current).name == path.name:
            log(f"reusing llama-server on :{port} ({path.name})")
            return False
        log(f"llama-server on :{port} has {Path(current).name if current else 'unknown'}, restarting for {path.name}")
        stop_server(port=port, log=log)

    SERVER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    server_log = SERVER_LOG_DIR / "llama-server.log"
    cmd = [
        LLAMA_SERVER, "-m", str(path),
        "-c", str(ctx),
        "--cache-type-k", "q8_0", "--cache-type-v", "q8_0",
        "-ngl", "99",
        "--port", str(port),
    ] + list(extra_args or [])
    log(f"starting llama-server: {path.name} ctx={ctx}")
    with open(server_log, "a") as lf:
        subprocess.Popen(cmd, stdout=lf, stderr=lf, start_new_session=True)

    deadline = time.time() + wait
    while time.time() < deadline:
        if server_up(port):
            log(f"llama-server up on :{port} after {wait - int(deadline - time.time())}s")
            return True
        time.sleep(3)
    raise LocalModelError(f"llama-server did not come up within {wait}s. See {server_log}")


def stop_server(port: int = DEFAULT_PORT, log=print) -> None:
    """Kill whatever llama-server owns `port`. Safe if nothing is running."""
    try:
        pids = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}"], capture_output=True, text=True, timeout=10
        ).stdout.split()
    except Exception:
        pids = []
    for pid in pids:
        try:
            os.kill(int(pid), signal.SIGTERM)
        except Exception:
            continue
    if pids:
        log(f"stopped llama-server on :{port}")
        for _ in range(20):
            if not server_up(port, timeout=1):
                return
            time.sleep(1)


# --------------------------------------------------------------------------- #
# completion
# --------------------------------------------------------------------------- #

def chatml(system: str, user: str, think: bool = False) -> str:
    """ChatML prompt. See MODELS[...]['think'] for when the empty think block is
    required: it disables Qwen3 reasoning so a grammar binds from token one."""
    tail = "<think>\n\n</think>\n\n" if think else ""
    return (
        f"<|im_start|>system\n{system}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        f"<|im_start|>assistant\n{tail}"
    )


def complete(
    prompt: str,
    grammar: str | None = None,
    n_predict: int = 2200,
    temperature: float = 0.2,
    top_p: float = 0.9,
    repeat_penalty: float = 1.05,
    stop: list[str] | None = None,
    timeout: int = 1800,
    port: int = DEFAULT_PORT,
    server: str | None = None,
) -> dict:
    """POST /completion. Returns the raw server response dict.

    cache_prompt reuses the KV prefix across calls, which is worth a lot once
    two calls in a row share a system prompt.
    """
    payload: dict = {
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": temperature,
        "top_p": top_p,
        "repeat_penalty": repeat_penalty,
        "cache_prompt": True,
        "stop": stop if stop is not None else ["<|im_end|>"],
    }
    if grammar:
        payload["grammar"] = grammar
    base = server or server_url(port)
    req = urllib.request.Request(
        f"{base}/completion",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def free_gb(path: Path | str = "/") -> float:
    return shutil.disk_usage(str(path)).free / 1e9


if __name__ == "__main__":
    import sys

    if "--stop" in sys.argv:
        if server_up():
            stop_server()
        else:
            print(f"nothing running on :{DEFAULT_PORT}")
        sys.exit(0)

    print(f"models dir: {MODELS_DIR}")
    for name in MODELS:
        try:
            path = model_path(name)
            print(f"  ok      {name:<16} {path.stat().st_size / 1e9:>5.1f} GB  {path}")
        except LocalModelError as e:
            print(f"  MISSING {name:<16} {e}")
    print(f"server on :{DEFAULT_PORT}: {'up' if server_up() else 'down'}")
    if server_up():
        print(f"  loaded: {loaded_model()}")
        print(f"  browser chat: http://127.0.0.1:{DEFAULT_PORT}")
    sys.exit(0)
