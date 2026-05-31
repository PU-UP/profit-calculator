"""从持仓截图经 MiniMax vision + text 动态解析标的金额，并汇总占比。

默认优先 mmx CLI（与原 Streamlit 一致）；无 mmx 时回退 httpx。
可通过环境变量 MINIMAX_BACKEND=mmx|httpx|auto 强制选择（默认 auto）。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

from profit_calc.minimax_client import load_config, resolve_vision_api, text_chat, vision_api_label
from profit_calc.minimax_client import vision_transcribe as _api_vision_transcribe

REPO_ROOT = Path(__file__).resolve().parents[1]
_SUBPROC_TEXT_KW = {"encoding": "utf-8", "errors": "replace"}

# 截图顶栏汇总项，不得当作持仓标的行
_SUMMARY_NAME_MARKERS = (
    "账户资产",
    "总资产",
    "总市值",
    "可用",
    "可取",
    "仓位",
    "浮动盈亏",
    "当日盈亏",
    "今日盈亏",
)

_CASH_ROW_NAMES = ("剩余资金", "可用资金", "可用", "现金", "可取")

VISION_TRANSCRIBE_PROMPT = """你是 OCR 与表格转写助手。请完整转写图片中与持仓、资产、仓位相关的整张表格文字：
包括顶部汇总区（账户资产、总市值、仓位%、可用/可取、浮动盈亏等）以及下方每一持仓行的名称、市值、现价、成本、浮动盈亏金额与浮动盈亏比例（%）等。
按人类阅读顺序输出（自上而下、从左到右），保留换行。
不要解释、不要摘要、不要评价，只输出转写正文。"""

TEXT_SYSTEM = """你是金融表格解析助手。用户将提供「截图转写文本」（典型为券商 App 持仓页）。

【概念区分（必须遵守）】
- account_assets（账户资产）：账户总资产，分母用于算占比；绝不是「总市值」。
- market_value（总市值）：已持仓证券市值合计；通常小于账户资产。
- 剩余资金 ≈ 账户资产 − 总市值（与「可用」资金一致或接近）。

【任务】
1) 从顶部汇总区读取 account_assets、market_value、position_pct（仓位%，数字不带%号）。
2) holdings 仅列出下方持仓明细中的证券/ETF/基金，每项 amount 填「市值」列金额（元）。
3) 不要把「账户资产」「总市值」「可用」「可取」「仓位」等汇总项放进 holdings。
4) 不要单独输出「剩余资金」行（程序会用账户资产−总市值计算）。
5) 若某持仓行有「仓位%」可填入 position_pct；没有则 null。
6) 每行若有「浮动盈亏」列：floating_pnl 填盈亏金额（元，亏损为负数，不带「元」）；floating_pnl_pct 填盈亏比例（数字不带%号，亏损为负）。
7) 不得臆造；看不清填 null。

【输出】只输出一个 JSON 对象，无 Markdown 围栏：
{
  "account_assets": 285027.25,
  "market_value": 224264.10,
  "position_pct": 78.68,
  "holdings": [
    {
      "name": "科创芯片",
      "code": "588290",
      "amount": 81595.8,
      "position_pct": 28.6,
      "floating_pnl": 19285.92,
      "floating_pnl_pct": 31.84
    }
  ]
}"""


@dataclass
class PositionSummary:
    """解析与校验后的仓位汇总。"""

    account_assets: float
    market_value: float
    cash: float
    df: pd.DataFrame
    checks: list[str] = field(default_factory=list)
    position_pct_reported: float | None = None
    backend: str = ""
    backend_mode: str = ""
    region: str = ""
    api_key_hint: str = ""
    transcript_chars: int = 0
    holdings_raw_count: int = 0
    vision_api: str = ""
    transcript_preview: str = ""


def _api_key_hint() -> str:
    key = (os.getenv("MINIMAX_API_KEY") or "").strip()
    if not key:
        return "未配置"
    if len(key) <= 8:
        return f"已配置（{len(key)} 字符）"
    return f"{key[:4]}…{key[-4:]}（{len(key)} 字符）"


def describe_recognition_backend() -> dict[str, str]:
    """供 UI 展示：当前将使用的识别后端与环境（不调用 API）。"""
    load_dotenv(REPO_ROOT / ".env", override=False)
    mode = (os.getenv("MINIMAX_BACKEND") or "auto").strip().lower()
    mmx_path = (os.getenv("MINIMAX_MMX_BIN") or "").strip() or (_find_mmx() or "")
    region = (os.getenv("MINIMAX_REGION") or "cn").strip().lower()
    if region not in ("cn", "global"):
        region = "cn"
    base_url = (os.getenv("MINIMAX_BASE_URL") or "").strip()

    if mode == "httpx":
        backend = "httpx"
        mode_desc = "httpx（MINIMAX_BACKEND=httpx）"
    elif mode == "mmx":
        if mmx_path:
            backend = "mmx"
            mode_desc = f"mmx（MINIMAX_BACKEND=mmx，{mmx_path}）"
        else:
            backend = "—"
            mode_desc = "mmx（已强制但未找到 mmx CLI）"
    elif mmx_path:
        backend = "mmx"
        mode_desc = f"auto → mmx（{mmx_path}）"
    else:
        backend = "httpx"
        mode_desc = "auto → httpx（无 mmx CLI，使用 Python 图文 API）"

    api_key = (os.getenv("MINIMAX_API_KEY") or "").strip()
    info: dict[str, str] = {
        "识别后端": backend,
        "后端选择": mode_desc,
        "MINIMAX_REGION": region,
        "API Key": _api_key_hint(),
        "Vision API": vision_api_label(resolve_vision_api(api_key)) if api_key else "—",
    }
    if base_url:
        info["MINIMAX_BASE_URL"] = base_url
    return info


def _find_mmx() -> str | None:
    bindir = REPO_ROOT / "node_modules" / ".bin"
    for name in ("mmx.cmd", "mmx.exe", "mmx"):
        p = bindir / name
        if p.is_file():
            return str(p)
    return shutil.which("mmx")


def _use_mmx_backend() -> bool:
    mode = (os.getenv("MINIMAX_BACKEND") or "auto").strip().lower()
    if mode == "httpx":
        return False
    if mode == "mmx":
        if not _find_mmx():
            raise RuntimeError("MINIMAX_BACKEND=mmx 但未找到 mmx，请在项目根目录执行 npm install。")
        return True
    return _find_mmx() is not None


def _mmx_prefix(mmx: str, api_key: str, region: str, base_url: str | None) -> list[str]:
    cmd = [mmx, "--api-key", api_key, "--region", region, "--non-interactive"]
    if base_url:
        cmd.extend(["--base-url", base_url])
    return cmd


def _run_mmx(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        **_SUBPROC_TEXT_KW,
    )


def _parse_vision_content(data: dict[str, Any]) -> str:
    if "error" in data:
        raise RuntimeError(json.dumps(data["error"], ensure_ascii=False))
    c = data.get("content")
    if isinstance(c, str) and c.strip():
        return c.strip()
    raise RuntimeError(f"vision 响应无 content：{json.dumps(data, ensure_ascii=False)[:800]}")


def _load_mmx_env() -> tuple[str, str, str, str | None, dict[str, str]]:
    load_dotenv(REPO_ROOT / ".env")
    api_key = (os.getenv("MINIMAX_API_KEY") or "").strip()
    if not api_key:
        raise RuntimeError("未设置 MINIMAX_API_KEY（请在 .env 中配置）。")

    mmx = (os.getenv("MINIMAX_MMX_BIN") or "").strip() or (_find_mmx() or "")
    if not mmx:
        raise RuntimeError("未找到 mmx，请在项目根目录执行 npm install。")

    region = (os.getenv("MINIMAX_REGION") or "cn").strip().lower()
    if region not in ("cn", "global"):
        region = "cn"
    base_url = (os.getenv("MINIMAX_BASE_URL") or "").strip() or None

    env = os.environ.copy()
    env.pop("MINIMAX_API_KEY", None)
    return api_key, mmx, region, base_url, env


def _vision_transcribe_mmx(
    mmx: str,
    prefix: list[str],
    env: dict[str, str],
    image: Path,
    timeout: int,
) -> str:
    cmd = [
        *prefix,
        "--timeout",
        str(timeout),
        "--output",
        "json",
        "vision",
        "describe",
        "--image",
        str(image.resolve()),
        "--prompt",
        VISION_TRANSCRIBE_PROMPT,
    ]
    proc = _run_mmx(cmd, cwd=REPO_ROOT, env=env, timeout=timeout + 30)
    out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or out or f"exit {proc.returncode}")[:4000])
    data = json.loads(out) if out else {}
    if not isinstance(data, dict):
        raise RuntimeError(out[:2000])
    return _parse_vision_content(data)


def _text_extract_parsed_mmx(
    mmx: str,
    prefix: list[str],
    env: dict[str, str],
    transcript: str,
    timeout: int,
) -> dict[str, Any]:
    user_body = "【截图转写】\n" + transcript + "\n\n请输出要求的 JSON。"
    messages = [
        {"role": "system", "content": TEXT_SYSTEM},
        {"role": "user", "content": user_body},
    ]
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".json",
        delete=False,
    ) as f:
        json.dump(messages, f, ensure_ascii=False)
        msg_path = f.name
    try:
        cmd = [
            *prefix,
            "--timeout",
            str(timeout),
            "--output",
            "json",
            "--temperature",
            "0.1",
            "text",
            "chat",
            "--messages-file",
            msg_path,
        ]
        proc = _run_mmx(cmd, cwd=REPO_ROOT, env=env, timeout=timeout + 60)
        out = (proc.stdout or "").strip()
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or out or f"exit {proc.returncode}")[:4000])
        return _parse_text_chat_json(out)
    finally:
        try:
            Path(msg_path).unlink(missing_ok=True)
        except OSError:
            pass


def _first_balanced_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    i = start
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        i += 1
    return None


def _relax_trailing_commas(s: str) -> str:
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r",(\s*])", r"\1", s)
        s = re.sub(r",(\s*})", r"\1", s)
    return s


def _try_json_loads(s: str) -> dict[str, Any]:
    obj = json.loads(s)
    if not isinstance(obj, dict):
        raise TypeError("root not object")
    return obj


def _parse_text_chat_json(stdout: str) -> dict[str, Any]:
    raw = (stdout or "").strip()
    if not raw:
        raise RuntimeError("text chat 输出为空")
    try:
        outer = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"text chat 外层非 JSON：{e}\n{raw[:1200]}") from e
    if isinstance(outer, dict) and "error" in outer:
        raise RuntimeError(json.dumps(outer["error"], ensure_ascii=False))
    text_parts: list[str] = []
    c = outer.get("content") if isinstance(outer, dict) else None
    if isinstance(c, str) and c.strip():
        text_parts.append(c.strip())
    elif isinstance(c, list):
        for block in c:
            if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
    if not text_parts and isinstance(outer, dict) and isinstance(outer.get("reply"), str):
        text_parts.append(outer["reply"])
    blob = "\n".join(text_parts).strip() if text_parts else raw
    return _extract_json_object(blob)


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text)

    raw = _first_balanced_json_object(text)
    if raw is None:
        raise RuntimeError(f"无法从模型输出中定位 JSON 对象（缺少配对花括号）：\n{text[:2000]}")

    relaxed = _relax_trailing_commas(raw)
    candidates = [raw] if raw == relaxed else [raw, relaxed]

    last_json_err: json.JSONDecodeError | None = None
    failed_cand = raw
    last_err: Exception | None = None
    for cand in candidates:
        try:
            return _try_json_loads(cand)
        except json.JSONDecodeError as e:
            last_json_err = e
            last_err = e
            failed_cand = cand
        except TypeError as e:
            last_err = e
            continue

    if last_json_err is not None:
        pos = last_json_err.pos
        lo = max(0, pos - 40)
        hi = min(len(failed_cand), pos + 40)
        snippet = failed_cand[lo:hi]
        raise RuntimeError(
            f"JSON 解析失败：{last_json_err}\n"
            f"出错片段附近（字符 {pos}）：{snippet!r}\n"
            f"原始对象前 500 字：{raw[:500]!r}"
        ) from last_json_err
    raise RuntimeError(
        f"模型输出根节点不是 JSON 对象：{last_err}\n原始前 500 字：{raw[:500]!r}"
    ) from last_err


def vision_transcribe(
    image: Path,
    *,
    timeout_vision: int = 120,
) -> str:
    """Vision 转写（供 CLI --print-transcript 等）。"""
    if _use_mmx_backend():
        api_key, mmx, region, base_url, env = _load_mmx_env()
        prefix = _mmx_prefix(mmx, api_key, region, base_url)
        return _vision_transcribe_mmx(mmx, prefix, env, image, timeout_vision)
    config = load_config(REPO_ROOT / ".env")
    return _api_vision_transcribe(
        image,
        prompt=VISION_TRANSCRIBE_PROMPT,
        timeout=timeout_vision,
        config=config,
    )


def _format_label(name: str, code: Any) -> str:
    name = (name or "").strip() or "（未命名）"
    if code is None:
        return name
    code_s = str(code).strip()
    if not code_s:
        return name
    if code_s in name:
        return name
    return f"{name} ({code_s})"


def _parse_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        amt = float(value)
        return amt if amt > 0 else None
    if isinstance(value, str):
        s = value.strip().replace(",", "").replace("，", "")
        if not s:
            return None
        try:
            amt = float(s)
            return amt if amt > 0 else None
        except ValueError:
            return None
    return None


def _parse_pct(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v if v >= 0 else None
    if isinstance(value, str):
        s = value.strip().replace("%", "").replace("％", "")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _parse_signed_number(value: Any) -> float | None:
    """解析可正可负的数值（如浮动盈亏金额）。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace(",", "").replace("，", "").replace("元", "")
        s = s.replace("+", "")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _parse_signed_pct(value: Any) -> float | None:
    """解析可正可负的百分比（如浮动盈亏比例）。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().replace("%", "").replace("％", "").replace("+", "")
        if not s:
            return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


def _is_summary_row(name: str) -> bool:
    n = (name or "").strip()
    if not n:
        return True
    for marker in _SUMMARY_NAME_MARKERS:
        if marker in n:
            return True
    for cash in _CASH_ROW_NAMES:
        if n == cash or n.startswith(cash):
            return True
    return False


def _near(a: float, b: float, *, rel: float = 0.02, abs_tol: float = 50.0) -> bool:
    if a <= 0 and b <= 0:
        return True
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def summarize_holdings(parsed: dict[str, Any]) -> PositionSummary:
    """
    以账户资产为分母汇总占比；剩余资金 = 账户资产 − 总市值（优先用顶栏总市值）。
    """
    checks: list[str] = []

    account_assets = _parse_amount(parsed.get("account_assets"))
    market_value_header = _parse_amount(parsed.get("market_value"))
    position_pct_reported = _parse_pct(parsed.get("position_pct"))

    holdings_raw = parsed.get("holdings")
    if not isinstance(holdings_raw, list):
        holdings_raw = []

    securities: list[dict[str, Any]] = []
    for item in holdings_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if _is_summary_row(name):
            continue
        amt = _parse_amount(item.get("amount"))
        if amt is None:
            continue
        securities.append(
            {
                "标的": _format_label(name, item.get("code")),
                "金额（元）": amt,
                "仓位%（识别）": _parse_pct(item.get("position_pct")),
                "浮动盈亏（元）": _parse_signed_number(item.get("floating_pnl")),
                "浮动比例（%）": _parse_signed_pct(item.get("floating_pnl_pct")),
            }
        )

    holdings_sum = sum(s["金额（元）"] for s in securities)

    if market_value_header is not None:
        market_value = market_value_header
        if holdings_sum > 0 and not _near(market_value, holdings_sum, rel=0.03):
            checks.append(
                f"⚠ 顶栏总市值 {market_value:,.2f} 与持仓市值合计 {holdings_sum:,.2f} 不一致，"
                f"占比按顶栏总市值计算。"
            )
    else:
        market_value = holdings_sum
        if holdings_sum > 0:
            checks.append("ℹ 未识别顶栏总市值，已用各持仓市值合计。")

    if account_assets is None:
        if market_value > 0 and holdings_sum > 0:
            account_assets = market_value  # 最差回退
            checks.append(
                "⚠ 未识别账户资产，暂以总市值作为分母（占比合计将为 100%，无剩余资金行）。"
            )
        elif holdings_sum > 0:
            account_assets = holdings_sum
            checks.append("⚠ 未识别账户资产与总市值，已用持仓合计作为总资产（请核对截图）。")
        else:
            empty = pd.DataFrame(
                columns=["标的", "金额（元）", "占比（%）", "浮动盈亏（元）", "浮动比例（%）"]
            )
            return PositionSummary(0.0, 0.0, 0.0, empty, ["⚠ 未识别到有效持仓与账户资产。"])

    # 剩余资金：账户资产 − 总市值（不用模型识别的「可用」行，避免歧义）
    cash = max(0.0, account_assets - market_value)
    if account_assets > market_value + 1.0:
        pass  # 正常
    elif market_value > account_assets + 1.0:
        checks.append(
            f"⚠ 总市值 {market_value:,.2f} 大于账户资产 {account_assets:,.2f}，"
            "可能把总市值误当作账户资产，请核对顶栏。"
        )
        cash = 0.0

    rows: list[dict[str, Any]] = []
    for s in securities:
        pct = round(s["金额（元）"] / account_assets * 100, 1) if account_assets > 0 else 0.0
        rows.append(
            {
                "标的": s["标的"],
                "金额（元）": s["金额（元）"],
                "占比（%）": pct,
                "浮动盈亏（元）": s.get("浮动盈亏（元）"),
                "浮动比例（%）": s.get("浮动比例（%）"),
            }
        )

    if cash > 0.5:
        cash_pct = round(cash / account_assets * 100, 1) if account_assets > 0 else 0.0
        rows.append(
            {
                "标的": "剩余资金",
                "金额（元）": round(cash, 2),
                "占比（%）": cash_pct,
                "浮动盈亏（元）": None,
                "浮动比例（%）": None,
            }
        )

    _df_cols = ["标的", "金额（元）", "占比（%）", "浮动盈亏（元）", "浮动比例（%）"]
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=_df_cols)

    # --- 校验 ---
    if position_pct_reported is not None and account_assets > 0 and market_value > 0:
        implied = market_value / account_assets * 100.0
        if _near(position_pct_reported, implied, rel=0.015, abs_tol=0.5):
            checks.append(
                f"✓ 仓位 {position_pct_reported:.2f}% ≈ 总市值/账户资产 ({implied:.2f}%)。"
            )
        else:
            checks.append(
                f"⚠ 顶栏仓位 {position_pct_reported:.2f}% 与 总市值/账户资产 {implied:.2f}% 不一致。"
            )

    if account_assets > 0 and market_value > 0:
        cash_from_position = account_assets * (1.0 - market_value / account_assets)
        if _near(cash, cash_from_position, rel=0.01, abs_tol=1.0):
            checks.append("✓ 剩余资金 ≈ 账户资产 × (1 − 仓位比例)。")

    pct_sum = float(df["占比（%）"].sum()) if not df.empty and "占比（%）" in df.columns else 0.0
    if account_assets > 0 and pct_sum > 0:
        if _near(pct_sum, 100.0, rel=0.02, abs_tol=1.5):
            checks.append(f"✓ 各占比合计 {pct_sum:.1f}% ≈ 100%。")
        else:
            checks.append(
                f"⚠ 各占比合计 {pct_sum:.1f}%，偏离 100%（识别可能有漏行或金额错误）。"
            )

    # 逐行仓位%（若截图有）
    for s in securities:
        reported = s.get("仓位%（识别）")
        if reported is None or account_assets <= 0:
            continue
        implied_row = s["金额（元）"] / account_assets * 100.0
        if not _near(reported, implied_row, rel=0.03, abs_tol=0.8):
            checks.append(
                f"⚠ {s['标的']}：识别仓位 {reported:.1f}% vs 按账户资产推算 {implied_row:.1f}%。"
            )

    return PositionSummary(
        account_assets=account_assets,
        market_value=market_value,
        cash=cash,
        df=df,
        checks=checks,
        position_pct_reported=position_pct_reported,
    )


def extract_holdings_from_image(
    image_path: Path,
    *,
    timeout_vision: int = 120,
    timeout_text: int = 120,
) -> PositionSummary:
    """从截图识别持仓，返回含校验信息的 PositionSummary。"""
    image = Path(image_path)
    if not image.is_file():
        raise FileNotFoundError(f"图片不存在：{image}")

    if _use_mmx_backend():
        api_key, mmx, region, base_url, env = _load_mmx_env()
        prefix = _mmx_prefix(mmx, api_key, region, base_url)
        transcript = _vision_transcribe_mmx(mmx, prefix, env, image, timeout_vision)
        parsed = _text_extract_parsed_mmx(mmx, prefix, env, transcript, timeout_text)
    else:
        config = load_config(REPO_ROOT / ".env")
        transcript = _api_vision_transcribe(
            image,
            prompt=VISION_TRANSCRIBE_PROMPT,
            timeout=timeout_vision,
            config=config,
        )
        user_body = "【截图转写】\n" + transcript + "\n\n请输出要求的 JSON。"
        messages = [
            {"role": "system", "content": TEXT_SYSTEM},
            {"role": "user", "content": user_body},
        ]
        raw_text = text_chat(
            messages,
            temperature=0.1,
            timeout=timeout_text,
            config=config,
        )
        parsed = _extract_json_object(raw_text)

    holdings_raw = parsed.get("holdings")
    holdings_raw_count = len(holdings_raw) if isinstance(holdings_raw, list) else 0
    diag = describe_recognition_backend()
    summary = summarize_holdings(parsed)
    preview = transcript.strip()
    if len(preview) > 200:
        preview = preview[:200] + "…"
    return replace(
        summary,
        backend=diag["识别后端"],
        backend_mode=diag["后端选择"],
        region=diag["MINIMAX_REGION"],
        api_key_hint=diag["API Key"],
        transcript_chars=len(transcript),
        holdings_raw_count=holdings_raw_count,
        vision_api=diag.get("Vision API", ""),
        transcript_preview=preview,
    )


def format_holdings_table(summary: PositionSummary) -> str:
    """CLI 用：打印简表与校验摘要。"""
    lines = [
        f"账户资产：{summary.account_assets:,.2f} 元",
        f"总市值：  {summary.market_value:,.2f} 元",
        f"剩余资金：{summary.cash:,.2f} 元（账户资产 − 总市值）",
        "",
    ]
    if summary.df.empty:
        lines.append("（未识别到有效持仓行）")
    else:
        lines.append(
            f"{'标的':<20} {'金额（元）':>12} {'占比（%）':>8} "
            f"{'浮动盈亏（元）':>14} {'浮动比例（%）':>10}"
        )
        lines.append("-" * 72)
        for _, row in summary.df.iterrows():
            pnl = row.get("浮动盈亏（元）")
            pnl_pct = row.get("浮动比例（%）")
            pnl_s = "—" if pd.isna(pnl) else f"{pnl:+,.2f}"
            pnl_pct_s = "—" if pd.isna(pnl_pct) else f"{pnl_pct:+.2f}%"
            lines.append(
                f"{str(row['标的']):<20} {row['金额（元）']:>12,.2f} {row['占比（%）']:>7.1f}% "
                f"{pnl_s:>14} {pnl_pct_s:>10}"
            )
    if summary.checks:
        lines.extend(["", "【校验】"])
        lines.extend(summary.checks)
    return "\n".join(lines)
