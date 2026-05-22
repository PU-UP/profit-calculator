#!/usr/bin/env python3
"""加载项目根目录 .env，校验 MiniMax CLI：auth + vision（可选 text 回退）。

密钥经 ``--api-key`` 传入，与 ``~/.mmx/config.json`` 脱钩。

用法（在项目根目录）::

    uv run python scripts/check_mmx_key.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]

# Windows 默认控制台编码常为 GBK，mmx 输出 UTF-8，需显式指定避免 decode 崩溃
_SUBPROC_TEXT_KW = {"encoding": "utf-8", "errors": "replace"}

# 官方静态资源，避免本地极小测试图触发内容安全误判
_VISION_TEST_IMAGE_URL = "https://file.cdn.minimax.io/public/MMX.png"


def _find_mmx() -> str | None:
    bindir = _ROOT / "node_modules" / ".bin"
    for name in ("mmx.cmd", "mmx.exe", "mmx"):
        p = bindir / name
        if p.is_file():
            return str(p)
    return shutil.which("mmx")


def _mmx_prefix(mmx: str, api_key: str, region: str) -> list[str]:
    return [
        mmx,
        "--api-key",
        api_key,
        "--region",
        region,
        "--non-interactive",
    ]


def _parse_vision_content(vdata: object) -> str | None:
    if not isinstance(vdata, dict):
        return None
    if "error" in vdata:
        return None
    c = vdata.get("content")
    if isinstance(c, str) and c.strip():
        return c.strip()
    return None


def _parse_text_chat_reply(obj: object) -> str | None:
    if not isinstance(obj, dict):
        return None
    if "error" in obj:
        return None
    r = obj.get("reply")
    if isinstance(r, str) and r.strip():
        return r.strip()
    choices = obj.get("choices")
    if isinstance(choices, list) and choices:
        c0 = choices[0]
        if isinstance(c0, dict):
            msg = c0.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    for k in ("text", "content", "result"):
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _run_text_smoke(prefix: list[str], env: dict[str, str]) -> tuple[bool, str]:
    cmd = [
        *prefix,
        "--timeout",
        "60",
        "--output",
        "json",
        "text",
        "chat",
        "--message",
        "只回复一个字：好",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
            **_SUBPROC_TEXT_KW,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return False, str(e)

    raw = (proc.stdout or "").strip()
    if proc.returncode != 0:
        return False, raw or (proc.stderr or "").strip() or f"exit {proc.returncode}"

    try:
        data = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return False, raw[:500] if raw else "(空)"

    reply = _parse_text_chat_reply(data)
    if reply:
        return True, reply[:200]
    return False, raw[:500] if raw else json.dumps(data, ensure_ascii=False)[:500]


def main() -> int:
    load_dotenv(_ROOT / ".env")
    api_key = (os.getenv("MINIMAX_API_KEY") or "").strip()
    if not api_key:
        print("错误：未设置 MINIMAX_API_KEY（请在 .env 中配置）。", file=sys.stderr)
        return 1

    mmx = (os.getenv("MINIMAX_MMX_BIN") or "").strip() or _find_mmx()
    if not mmx:
        print(
            "错误：未找到 mmx。请在项目根目录执行 npm install，或设置环境变量 MINIMAX_MMX_BIN。",
            file=sys.stderr,
        )
        return 1

    region = (os.getenv("MINIMAX_REGION") or "cn").strip().lower()
    if region not in ("cn", "global"):
        region = "cn"

    env = os.environ.copy()
    env.pop("MINIMAX_API_KEY", None)

    prefix = _mmx_prefix(mmx, api_key, region)

    # --- 1) auth status ---
    cmd_auth = [*prefix, "--output", "json", "--timeout", "120", "auth", "status"]
    try:
        proc = subprocess.run(
            cmd_auth,
            cwd=str(_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=130,
            **_SUBPROC_TEXT_KW,
        )
    except FileNotFoundError:
        print(f"错误：无法执行 {mmx}（是否已安装 Node / npm？）", file=sys.stderr)
        return 1
    except subprocess.TimeoutExpired:
        print("错误：mmx auth status 超时。", file=sys.stderr)
        return 1

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        print(f"mmx auth status 失败，退出码 {proc.returncode}", file=sys.stderr)
        if err:
            print(err, file=sys.stderr)
        if out:
            print(out, file=sys.stderr)
        return proc.returncode or 1

    try:
        auth_data = json.loads(out) if out else {}
    except json.JSONDecodeError:
        print("认证状态（非 JSON）：", out or "(空)", file=sys.stderr)
        return 1

    print(json.dumps(auth_data, ensure_ascii=False, indent=2))
    sys.stdout.flush()
    print()
    print("【1/2】验证成功：API 密钥有效（mmx auth status）。")
    sys.stdout.flush()

    # --- 2) vision describe（远程图片 URL）---
    cmd_vision = [
        *prefix,
        "--timeout",
        "120",
        "--output",
        "json",
        "vision",
        "describe",
        "--image",
        _VISION_TEST_IMAGE_URL,
        "--prompt",
        "请用一句话描述图片中的主色或图形（不超过二十字）。",
    ]
    try:
        proc_v = subprocess.run(
            cmd_vision,
            cwd=str(_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=130,
            **_SUBPROC_TEXT_KW,
        )
    except subprocess.TimeoutExpired:
        print("错误：mmx vision describe 超时。", file=sys.stderr)
        return 1

    vout = (proc_v.stdout or "").strip()
    verr = (proc_v.stderr or "").strip()
    vision_ok = proc_v.returncode == 0
    vdata: dict | None = None
    if vision_ok:
        try:
            parsed = json.loads(vout) if vout else {}
            vdata = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            vision_ok = False

    content: str | None = None
    if vision_ok and vdata is not None:
        content = _parse_vision_content(vdata)

    if vision_ok and content:
        preview = content.replace("\n", " ")[:200]
        print()
        print("【2/2】验证成功：视觉接口可用（mmx vision describe）。")
        print(f"模型回复摘要：{preview}")
        sys.stdout.flush()
        print()
        print("全部验证通过。")
        return 0

    # vision 失败时打印原因，并用 text chat 证明 CLI 与 API 仍可用
    print()
    print("【2/2】视觉接口未通过，详情如下：", file=sys.stderr)
    if verr:
        print(verr, file=sys.stderr)
    if vout:
        print(vout, file=sys.stderr)
    sys.stderr.flush()

    ok_text, detail = _run_text_smoke(prefix, env)
    print()
    if ok_text:
        print("补充：文本接口验证成功（mmx text chat），CLI 与密钥可用。")
        print(f"模型回复摘要：{detail}")
        print()
        print("部分验证通过：auth 与 text 正常；vision 请检查上方报错或换图重试。")
        return 0

    print("补充：文本接口也未通过。", file=sys.stderr)
    print(detail, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
