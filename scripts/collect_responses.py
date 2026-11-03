#!/usr/bin/env python3
import argparse
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

DEFAULT_API_KEY_ENV = {
    "openai-compatible": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
}


def load_env(path: Path = ENV_PATH) -> None:
    """Load KEY=value lines from .env without overriding variables already set."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip().strip("'\"")
        if key and value:
            os.environ.setdefault(key, value)


load_env()

# Sampling temperature for collected responses. Judging keeps the default of 0.
TEMPERATURE = 0.0


def read_jsonl(path: Path) -> List[Dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def existing_ids(path: Path) -> set:
    if not path.exists():
        return set()
    return {row["id"] for row in read_jsonl(path) if row.get("response", "").strip()}


RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}


def post_json(url: str, payload: Dict, headers: Dict, max_retries: int = 5) -> Dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if exc.code not in RETRYABLE_HTTP_CODES or attempt == max_retries:
                raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
            delay = min(60, 2 ** attempt)
            print(f"HTTP {exc.code}; retrying in {delay}s")
            time.sleep(delay)
        except (urllib.error.URLError, TimeoutError, socket.timeout, ssl.SSLError, ConnectionError) as exc:
            if attempt == max_retries:
                raise RuntimeError(f"Network error: {exc}") from exc
            delay = min(60, 2 ** attempt)
            print(f"Network error; retrying in {delay}s")
            time.sleep(delay)
    raise RuntimeError("Request failed after retries")


def collect_openai_compatible(
    prompt: str, model: str, base_url: str, api_key: str, max_tokens: int
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": TEMPERATURE,
    }
    if max_tokens > 0:
        payload["max_tokens"] = max_tokens
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "FaithRightsBench/0.1",
    }
    data = post_json(url, payload, headers)
    return data["choices"][0]["message"]["content"]


def collect_ollama(prompt: str, model: str, base_url: str, max_tokens: int) -> str:
    url = base_url.rstrip("/") + "/api/chat"
    options = {"temperature": TEMPERATURE}
    if max_tokens > 0:
        options["num_predict"] = max_tokens
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": options,
    }
    data = post_json(url, payload, {"Content-Type": "application/json"})
    return data["message"]["content"]


def collect_gemini(
    prompt: str, model: str, base_url: str, api_key: str, max_tokens: int
) -> str:
    url = base_url.rstrip("/") + f"/v1beta/models/{model}:generateContent"
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": TEMPERATURE,
        },
    }
    if max_tokens > 0:
        payload["generationConfig"]["maxOutputTokens"] = max_tokens
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    data = post_json(url, payload, headers)
    parts = data["candidates"][0]["content"].get("parts", [])
    return "\n".join(part.get("text", "") for part in parts).strip()


def collect_anthropic(
    prompt: str, model: str, base_url: str, api_key: str, max_tokens: int
) -> str:
    url = base_url.rstrip("/") + "/v1/messages"
    payload = {
        "model": model,
        "max_tokens": max_tokens if max_tokens > 0 else 1024,
        "temperature": TEMPERATURE,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "User-Agent": "FaithRightsBench/0.1",
    }
    data = post_json(url, payload, headers)
    return "\n".join(
        part.get("text", "")
        for part in data.get("content", [])
        if part.get("type") == "text"
    ).strip()


def iter_prompts(rows: List[Dict], limit: int) -> Iterable[Dict]:
    if limit <= 0:
        yield from rows
    else:
        yield from rows[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect LLM responses for FaithRightsBench prompts."
    )
    parser.add_argument("--input", default="data/robust/prompts.jsonl")
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--provider",
        choices=["openai-compatible", "ollama", "gemini", "groq", "anthropic"],
        required=True,
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--api-key-env",
        default=None,
        help="Environment variable holding the API key. Defaults to the provider's usual name.",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature (default 0). Use e.g. 0.7 to draw independent samples.",
    )
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=0,
        help="Optional cap on generated response tokens. Use this for rate-limited APIs.",
    )
    args = parser.parse_args()
    args.api_key_env = args.api_key_env or DEFAULT_API_KEY_ENV.get(args.provider, "")
    global TEMPERATURE
    TEMPERATURE = args.temperature

    input_path = ROOT / args.input
    output_path = ROOT / args.output
    prompts = read_jsonl(input_path)
    done = existing_ids(output_path)

    if args.provider == "openai-compatible":
        base_url = args.base_url or "https://api.openai.com/v1"
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            raise SystemExit(
                f"Missing API key. Set {args.api_key_env}, or pass --api-key-env NAME."
            )
    elif args.provider == "groq":
        base_url = args.base_url or "https://api.groq.com/openai/v1"
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            raise SystemExit(
                f"Missing API key. Set {args.api_key_env}, or pass --api-key-env NAME."
            )
    elif args.provider == "gemini":
        base_url = args.base_url or "https://generativelanguage.googleapis.com"
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            raise SystemExit(
                f"Missing API key. Set {args.api_key_env}, or pass --api-key-env NAME."
            )
    elif args.provider == "anthropic":
        base_url = args.base_url or "https://api.anthropic.com"
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            raise SystemExit(
                f"Missing API key. Set {args.api_key_env}, or pass --api-key-env NAME."
            )
    else:
        base_url = args.base_url or "http://localhost:11434"
        api_key = ""

    total = 0
    for row in iter_prompts(prompts, args.limit):
        if row["id"] in done:
            continue

        print(f"Collecting {row['id']} with {args.model}")
        if args.provider in {"openai-compatible", "groq"}:
            response = collect_openai_compatible(
                row["prompt"], args.model, base_url, api_key, args.max_tokens
            )
        elif args.provider == "gemini":
            response = collect_gemini(
                row["prompt"], args.model, base_url, api_key, args.max_tokens
            )
        elif args.provider == "anthropic":
            response = collect_anthropic(
                row["prompt"], args.model, base_url, api_key, args.max_tokens
            )
        else:
            response = collect_ollama(row["prompt"], args.model, base_url, args.max_tokens)

        append_jsonl(
            output_path,
            {
                "id": row["id"],
                "model": args.model,
                "provider": args.provider,
                "temperature": args.temperature,
                "response": response,
            },
        )
        total += 1
        time.sleep(args.sleep)

    print(f"Wrote {total} new responses to {output_path}")


if __name__ == "__main__":
    main()
