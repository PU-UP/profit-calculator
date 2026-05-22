#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交易小算盘：NiceGUI 版 + PWA。

启动方式：python nicegui_app.py
默认端口 8001，可通过环境变量 PORT 或命令行参数覆盖。
"""
from __future__ import annotations

import json
import os
import struct
import sys
import zlib
from pathlib import Path

from nicegui import app, ui

# ── 端口 ──────────────────────────────────────────────────────────
DEFAULT_PORT = 8001


def get_port() -> int:
    if len(sys.argv) > 1:
        return int(sys.argv[1])
    if os.environ.get("PORT"):
        return int(os.environ["PORT"])
    return DEFAULT_PORT


# ── PWA 配置 ─────────────────────────────────────────────────────
PWA_MANIFEST = {
    "name": "交易小算盘",
    "short_name": "小算盘",
    "description": "做T净收益 · 仓位占比 · 涨跌幅计算",
    "start_url": "/",
    "display": "standalone",
    "background_color": "#ffffff",
    "theme_color": "#1976d2",
    "icons": [
        {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png"},
        {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png"},
    ],
}

# 生成 static 目录和文件
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)

manifest_path = static_dir / "manifest.json"
manifest_path.write_text(json.dumps(PWA_MANIFEST, ensure_ascii=False, indent=2), encoding="utf-8")


def _create_png(width: int, height: int, rgba: tuple = (25, 118, 210, 255)) -> bytes:
    """生成纯色 PNG 占位图标。"""
    def chunk(chunk_type: bytes, data: bytes) -> bytes:
        c = chunk_type + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
    raw = b""
    for _ in range(height):
        raw += b"\x00" + bytes(rgba) * width
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


# 尝试用 Pillow 生成带文字的图标，否则退回纯色
for size in [192, 512]:
    icon_path = static_dir / f"icon-{size}.png"
    if not icon_path.exists():
        try:
            from PIL import Image, ImageDraw, ImageFont

            img = Image.new("RGBA", (size, size), (25, 118, 210, 255))
            draw = ImageDraw.Draw(img)
            text = "算"
            font_size = size // 3
            font = None
            for path in [
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/System/Library/Fonts/PingFang.ttc",
            ]:
                try:
                    font = ImageFont.truetype(path, font_size)
                    break
                except (OSError, IOError):
                    continue
            if font is None:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (size - tw) // 2
            y = (size - th) // 2 - bbox[1]
            draw.text((x, y), text, fill="white", font=font)
            img.save(icon_path, "PNG")
        except ImportError:
            icon_path.write_bytes(_create_png(size, size))

# 挂载 static 目录
app.add_static_files("/static", str(static_dir))


# ── 主页面 ───────────────────────────────────────────────────────

@ui.page("/")
def main_page():
    """主页面：两个顶级 Tab（计算器 + 仓位占比）。"""
    # 用户级持久化状态
    user_data = app.storage.user
    hist_t = user_data.setdefault("hist_t", [])
    hist_p2pr = user_data.setdefault("hist_p2pr", [])
    hist_pr2p = user_data.setdefault("hist_pr2p", [])
    # 清理旧版误入 user 存储的仓位结果（含 DataFrame，无法 JSON 序列化）
    user_data.pop("pos_state", None)

    # 深色模式
    dark = ui.dark_mode(False)

    # 顶部栏
    with ui.header().classes("items-center justify-between"):
        ui.label("交易小算盘").classes("text-h6 font-bold")
        ui.button(icon="dark_mode", on_click=dark.toggle).props("flat round")

    # 主内容区
    with ui.column().classes("w-full max-w-2xl mx-auto q-pa-md"):
        with ui.tabs().classes("w-full") as tabs:
            ui.tab("profit_calc", label="计算器", icon="calculate")
            ui.tab("position_table", label="仓位占比", icon="pie_chart")

        with ui.tab_panels(tabs, value="profit_calc").classes("w-full"):
            with ui.tab_panel("profit_calc"):
                from profit_calc.nicegui_calc import render as render_calc

                def on_calc_update():
                    pass  # 历史已就地修改

                render_calc(hist_t, hist_p2pr, hist_pr2p, on_calc_update)

            with ui.tab_panel("position_table"):
                from profit_calc.nicegui_position import render as render_pos

                render_pos()


# ── HTML head 注入 PWA meta ─────────────────────────────────────

ui.add_head_html(
    '<link rel="manifest" href="/static/manifest.json">'
    '<meta name="theme-color" content="#1976d2">'
    '<meta name="apple-mobile-web-app-capable" content="yes">'
    '<meta name="apple-mobile-web-app-status-bar-style" content="default">'
    '<meta name="apple-mobile-web-app-title" content="小算盘">'
    '<link rel="apple-touch-icon" href="/static/icon-192.png">',
    shared=True,
)

# ── 启动 ─────────────────────────────────────────────────────────
_storage_secret = (os.environ.get("NICEGUI_STORAGE_SECRET") or "").strip()
if not _storage_secret:
    _storage_secret = "profit-calculator-nicegui-dev"

_icon_192 = static_dir / "icon-192.png"
_favicon: str | Path = _icon_192 if _icon_192.is_file() else "🧮"

ui.run(
    port=get_port(),
    title="交易小算盘",
    favicon=_favicon,
    reload=False,
    show=False,
    storage_secret=_storage_secret,
)
