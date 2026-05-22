#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯 Python MiniMax API 客户端，替代 mmx CLI（Node.js）。

Vision：POST /anthropic/v1/messages（图片 base64 嵌入 content）
Text：POST /v1/chat/completions（OpenAI 兼容）
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

# ── 区域 → Base URL ──────────────────────────────────────────────
_REGION_URLS: dict[str, str] = {
    "cn": "https://api.minimaxi.com",
    "global": "https://api.minimax.io",
}

# ── 默认模型 ─────────────────────────────────────────────────────
_DEFAULT_VISION_MODEL = "MiniMax-M2.7"
_DEFAULT_TEXT_MODEL = "MiniMax-M2.7"


def load_config(env_path: Path | None = None) -> dict[str, Any]:
    """从 .env 加载 MiniMax 配置。"""
    if env_path and env_path.is_file():
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)

    api_key = (os.getenv("MINIMAX_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("未设置 MINIMAX_API_KEY（请在 .env 中配置）。")

    region = (os.getenv("MINIMAX_REGION") or "cn").strip().lower()
    if region not in _REGION_URLS:
        region = "cn"

    base_url = (os.getenv("MINIMAX_BASE_URL") or "").strip() or _REGION_URLS[region]

    return {
        "api_key": api_key,
        "region": region,
        "base_url": base_url.rstrip("/"),
    }


# ── Vision（/anthropic/v1/messages）──────────────────────────────
def vision_transcribe(
    image_path: Path,
    *,
    prompt: str,
    model: str = _DEFAULT_VISION_MODEL,
    timeout: int = 120,
    config: dict[str, Any] | None = None,
) -> str:
    """调用 MiniMax Vision API 转写图片，返回文本内容。

    MiniMax Vision 必须走 /anthropic/v1/messages 端点，
    图片以 base64 嵌入 content 中的 image 块。
    """
    if config is None:
        config = load_config()

    image_path = Path(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"图片不存在：{image_path}")

    # 读取图片并编码 base64
    img_bytes = image_path.read_bytes()
    b64 = base64.b64encode(img_bytes).decode("ascii")

    # 推断 MIME
    suffix = image_path.suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    mime = mime_map.get(suffix, "image/png")

    url = f"{config['base_url']}/anthropic/v1/messages"
    headers = {
        "x-api-key": config["api_key"],
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": model,
        "max_tokens": 4096,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ],
    }

    with httpx.Client(timeout=timeout + 30) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    # 解析响应
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(json.dumps(data["error"], ensure_ascii=False))

    content = data.get("content")
    if isinstance(content, list):
        texts = [b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text" and b.get("text")]
        return "\n".join(texts).strip()
    if isinstance(content, str) and content.strip():
        return content.strip()

    raise RuntimeError(f"Vision 响应无有效内容：{json.dumps(data, ensure_ascii=False)[:800]}")


# ── Text（/v1/chat/completions，OpenAI 兼容）────────────────────
def text_chat(
    messages: list[dict[str, str]],
    *,
    model: str = _DEFAULT_TEXT_MODEL,
    temperature: float = 0.1,
    timeout: int = 120,
    config: dict[str, Any] | None = None,
) -> str:
    """调用 MiniMax Text API（OpenAI 兼容），返回助手回复文本。"""
    if config is None:
        config = load_config()

    url = f"{config['base_url']}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    with httpx.Client(timeout=timeout + 30) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()

    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(json.dumps(data["error"], ensure_ascii=False))

    choices = data.get("choices", [])
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message", {})
        content = msg.get("content", "")
        if content and content.strip():
            return content.strip()

    raise RuntimeError(f"Text 响应无有效内容：{json.dumps(data, ensure_ascii=False)[:800]}")
