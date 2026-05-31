#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纯 Python MiniMax API 客户端，替代 mmx CLI（Node.js）。

Vision（Coding Plan / sk-cp 密钥）：POST /v1/coding_plan/vlm（与 mmx vision describe 相同）
Vision（开放平台接口密钥）：POST /v1/text/chatcompletion_v2（image_url + Data URL）
Text：POST /v1/chat/completions（OpenAI 兼容）
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Literal

import httpx
from dotenv import load_dotenv

# ── 区域 → Base URL ──────────────────────────────────────────────
_REGION_URLS: dict[str, str] = {
    "cn": "https://api.minimaxi.com",
    "global": "https://api.minimax.io",
}

VisionApiMode = Literal["coding_plan", "chat"]

# ── 默认模型 ─────────────────────────────────────────────────────
_DEFAULT_VISION_MODEL = "MiniMax-M2.7"
_DEFAULT_TEXT_MODEL = "MiniMax-M2.7"
_CHAT_COMPLETION_V2 = "/v1/text/chatcompletion_v2"
_CODING_PLAN_VLM = "/v1/coding_plan/vlm"


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
    vision_model = (os.getenv("MINIMAX_VISION_MODEL") or _DEFAULT_VISION_MODEL).strip()
    vision_api = resolve_vision_api(api_key)

    return {
        "api_key": api_key,
        "region": region,
        "base_url": base_url.rstrip("/"),
        "vision_model": vision_model,
        "vision_api": vision_api,
    }


def resolve_vision_api(api_key: str) -> VisionApiMode:
    """选择 Vision 调用方式：Coding Plan 密钥须走 /v1/coding_plan/vlm。"""
    mode = (os.getenv("MINIMAX_VISION_API") or "auto").strip().lower()
    if mode in ("coding_plan", "vlm", "coding-plan"):
        return "coding_plan"
    if mode in ("chat", "chatcompletion_v2", "text"):
        return "chat"
    if api_key.startswith("sk-cp"):
        return "coding_plan"
    return "chat"


def vision_api_label(mode: VisionApiMode) -> str:
    return "coding_plan/vlm" if mode == "coding_plan" else "chatcompletion_v2"


def _auth_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _raise_if_api_error(data: dict[str, Any]) -> None:
    if "error" in data:
        raise RuntimeError(json.dumps(data["error"], ensure_ascii=False))
    base_resp = data.get("base_resp")
    if isinstance(base_resp, dict):
        code = base_resp.get("status_code")
        if code not in (None, 0):
            msg = base_resp.get("status_msg") or base_resp
            raise RuntimeError(json.dumps(msg, ensure_ascii=False))


def _parse_chat_completion_content(data: dict[str, Any], *, context: str) -> str:
    _raise_if_api_error(data)
    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if isinstance(msg, dict):
            content = msg.get("content", "")
            if isinstance(content, str) and content.strip():
                return content.strip()
    raise RuntimeError(f"{context}响应无有效内容：{json.dumps(data, ensure_ascii=False)[:800]}")


def _parse_vlm_content(data: dict[str, Any]) -> str:
    _raise_if_api_error(data)
    content = data.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    raise RuntimeError(f"Vision(vlm) 响应无 content：{json.dumps(data, ensure_ascii=False)[:800]}")


def _image_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    return mime_map.get(suffix, "image/png")


def _image_data_url(image_path: Path) -> str:
    mime = _image_mime(image_path)
    b64 = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _vision_transcribe_coding_plan(
    *,
    prompt: str,
    image_url: str,
    config: dict[str, Any],
    timeout: int,
) -> str:
    url = f"{config['base_url']}{_CODING_PLAN_VLM}"
    body = {"prompt": prompt, "image_url": image_url}
    with httpx.Client(timeout=timeout + 30) as client:
        resp = client.post(url, headers=_auth_headers(config["api_key"]), json=body)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Vision(vlm) 响应格式异常：{data!r}")
    return _parse_vlm_content(data)


def _vision_transcribe_chat(
    *,
    prompt: str,
    image_url: str,
    model: str,
    config: dict[str, Any],
    timeout: int,
) -> str:
    url = f"{config['base_url']}{_CHAT_COMPLETION_V2}"
    body: dict[str, Any] = {
        "model": model,
        "max_completion_tokens": 8192,
        "temperature": 0.1,
        "messages": [
            {
                "role": "user",
                "name": "用户",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
    }
    with httpx.Client(timeout=timeout + 30) as client:
        resp = client.post(url, headers=_auth_headers(config["api_key"]), json=body)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, dict):
        raise RuntimeError(f"Vision(chat) 响应格式异常：{data!r}")
    return _parse_chat_completion_content(data, context="Vision")


def vision_transcribe(
    image_path: Path,
    *,
    prompt: str,
    model: str | None = None,
    timeout: int = 120,
    config: dict[str, Any] | None = None,
) -> str:
    """调用 MiniMax Vision 转写图片，返回文本内容。"""
    if config is None:
        config = load_config()

    image_path = Path(image_path)
    if not image_path.is_file():
        raise FileNotFoundError(f"图片不存在：{image_path}")

    image_url = _image_data_url(image_path)
    mode: VisionApiMode = config.get("vision_api") or resolve_vision_api(config["api_key"])

    if mode == "coding_plan":
        return _vision_transcribe_coding_plan(
            prompt=prompt,
            image_url=image_url,
            config=config,
            timeout=timeout,
        )

    use_model = model or config.get("vision_model") or _DEFAULT_VISION_MODEL
    return _vision_transcribe_chat(
        prompt=prompt,
        image_url=image_url,
        model=use_model,
        config=config,
        timeout=timeout,
    )


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
    body = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    with httpx.Client(timeout=timeout + 30) as client:
        resp = client.post(url, headers=_auth_headers(config["api_key"]), json=body)
        resp.raise_for_status()
        data = resp.json()

    if not isinstance(data, dict):
        raise RuntimeError(f"Text 响应格式异常：{data!r}")
    return _parse_chat_completion_content(data, context="Text")
