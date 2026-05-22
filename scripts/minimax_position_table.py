#!/usr/bin/env python3
"""
从持仓截图识别各标的金额与占比（CLI）。

依赖：项目根目录 .env（MINIMAX_API_KEY、MINIMAX_REGION=cn）；通过 Python httpx 调用 MiniMax API。

用法（在项目根目录）::

    uv run python scripts/minimax_position_table.py
    uv run python scripts/minimax_position_table.py screenshots/my.png
    uv run python scripts/minimax_position_table.py screenshots/my.png --print-transcript
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from profit_calc.position_extract import (  # noqa: E402
    REPO_ROOT,
    extract_holdings_from_image,
    format_holdings_table,
    vision_transcribe,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="从截图提取持仓金额与占比")
    parser.add_argument(
        "image",
        nargs="?",
        default=str(REPO_ROOT / "screenshots" / "table.png"),
        help="截图路径（默认 screenshots/table.png）",
    )
    parser.add_argument("--timeout-vision", type=int, default=120)
    parser.add_argument("--timeout-text", type=int, default=120)
    parser.add_argument(
        "--print-transcript",
        action="store_true",
        help="将 vision 转写全文打印到 stderr",
    )
    args = parser.parse_args()

    image = Path(args.image)
    if not image.is_file():
        print(f"错误：图片不存在：{image}", file=sys.stderr)
        return 1

    if args.print_transcript:
        try:
            transcript = vision_transcribe(image, timeout_vision=args.timeout_vision)
        except Exception as e:
            print(f"vision 调用失败：{e}", file=sys.stderr)
            return 1
        print("--- vision 转写 ---", file=sys.stderr)
        print(transcript, file=sys.stderr)
        print("--- end ---", file=sys.stderr)

    try:
        summary = extract_holdings_from_image(
            image,
            timeout_vision=args.timeout_vision,
            timeout_text=args.timeout_text,
        )
    except Exception as e:
        print(f"识别失败：{e}", file=sys.stderr)
        return 1

    print(format_holdings_table(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
