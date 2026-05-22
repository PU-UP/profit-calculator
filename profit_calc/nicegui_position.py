#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NiceGUI：上传持仓截图，展示各标的金额与占比。"""
from __future__ import annotations

import math
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from nicegui import run, ui

from profit_calc.position_extract import PositionSummary, extract_holdings_from_image

# 仓位结果仅会话内缓存（含 DataFrame，不能写入 app.storage.user）
_last_summary: PositionSummary | None = None

_NA_SLASH = "/"


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if pd.isna(value):
        return True
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("", "nan", "none", "null"):
            return True
    return False


def _notify_brief(message: str, *, type_: str, ms: int = 12000) -> None:
    """结果类提示：显示更久，避免一闪而过。"""
    ui.notify(message, type=type_, timeout=ms, position="top", multi_line=True)


def _render_position_result(summary, container) -> None:
    """在指定容器内渲染 PositionSummary 结果。"""
    with container:
        # 三个大数字
        with ui.row().classes("w-full gap-4"):
            with ui.card().classes("flex-1"):
                ui.label("账户资产（元）").classes("text-caption")
                ui.label(f"{summary.account_assets:,.2f}").classes("text-h6 font-bold")
            with ui.card().classes("flex-1"):
                ui.label("总市值（元）").classes("text-caption")
                ui.label(f"{summary.market_value:,.2f}").classes("text-h6 font-bold")
            with ui.card().classes("flex-1"):
                ui.label("剩余资金（元）").classes("text-caption")
                ui.label(f"{summary.cash:,.2f}").classes("text-h6 font-bold")

        # 持仓表格
        df = summary.df
        if df.empty:
            ui.label("未识别到有效持仓行，请换图或重试。").classes("text-warning")
        else:
            columns = []
            for col in df.columns:
                align = "left" if col == "标的" else "right"
                columns.append({"name": col, "label": col, "field": col, "align": align, "sortable": False})

            rows = df.to_dict("records")
            for row in rows:
                if "金额（元）" in row and not _is_missing(row["金额（元）"]):
                    row["金额（元）"] = f"{float(row['金额（元）']):,.2f}"
                if "占比（%）" in row and not _is_missing(row["占比（%）"]):
                    row["占比（%）"] = f"{float(row['占比（%）']):.1f}%"
                if "浮动盈亏（元）" in row:
                    v = row["浮动盈亏（元）"]
                    row["浮动盈亏（元）"] = (
                        f"{float(v):+,.2f}" if not _is_missing(v) else _NA_SLASH
                    )
                if "浮动比例（%）" in row:
                    v = row["浮动比例（%）"]
                    row["浮动比例（%）"] = (
                        f"{float(v):+.2f}%" if not _is_missing(v) else _NA_SLASH
                    )

            ui.table(
                columns=columns,
                rows=rows,
                row_key="标的",
            ).classes("w-full").props('flat dense')

        # 校验结果
        if summary.checks:
            has_warning = any(c.startswith("⚠") for c in summary.checks)
            with ui.expansion("校验结果", icon="warning" if has_warning else "check_circle",
                              value=has_warning).classes("w-full"):
                for line in summary.checks:
                    if line.startswith("⚠"):
                        ui.label(line).classes("text-warning")
                    elif line.startswith("✓"):
                        ui.label(line).classes("text-positive")
                    else:
                        ui.label(line).classes("text-caption")

        ui.label("数据来自截图识别，请核对；占比分母为账户资产，非总市值。").classes("text-caption")


def render() -> None:
    """渲染仓位占比界面。"""
    global _last_summary
    ui.label("仓位占比").classes("text-h6 font-bold")
    ui.label(
        "以截图顶栏「账户资产」为总资产；各证券占比为市值/账户资产；"
        "浮动盈亏与比例为截图持仓行识别值；"
        "剩余资金 = 账户资产 − 总市值（不采用易混淆的「可用」识别值）。"
    ).classes("text-caption q-mb-md")

    # 高级设置
    with ui.expansion("高级设置", icon="settings").classes("w-full q-mb-md"):
        timeout_vision = ui.number(value=120, label="vision 超时（秒）", min=30, max=300, step=10)
        timeout_text = ui.number(value=120, label="text 超时（秒）", min=30, max=300, step=10)

    # 文件上传（NiceGUI 3.x：UploadEventArguments.file）
    uploaded_path: dict[str, Path | None] = {"path": None}

    async def handle_upload(e) -> None:
        """处理文件上传，保存到临时文件。"""
        file = e.file
        suffix = Path(file.name).suffix or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp_path = Path(tmp.name)
        await file.save(tmp_path)
        old = uploaded_path.get("path")
        if old is not None and old != tmp_path and old.exists():
            try:
                old.unlink()
            except OSError:
                pass
        uploaded_path["path"] = tmp_path
        status_label.text = f"已上传：{file.name}，可点击「识别仓位」。"
        _notify_brief(f"已上传：{file.name}", type_="positive", ms=6000)

    ui.upload(
        label="持仓截图",
        on_upload=handle_upload,
        auto_upload=True,
        multiple=False,
    ).props('accept=".png,.jpg,.jpeg,.webp"').classes("w-full")

    status_label = ui.label("上传截图后点击「识别仓位」。").classes(
        "text-body2 w-full q-my-sm min-h-[1.5rem]"
    )

    async def do_extract():
        path = uploaded_path.get("path")
        if path is None:
            status_label.text = "请先上传截图。"
            _notify_brief("请先上传截图", type_="warning")
            return

        extract_btn.props("loading")
        extract_btn.disable()
        status_label.text = "正在识别截图（vision + 解析），请稍候，通常需 1–2 分钟…"
        try:
            summary = await run.io_bound(
                extract_holdings_from_image,
                path,
                timeout_vision=int(timeout_vision.value),
                timeout_text=int(timeout_text.value),
            )
            _last_summary = summary

            result_container.clear()
            _render_position_result(summary, result_container)
            n = len(summary.df)
            if n == 0:
                status_label.text = "识别结束：未找到有效持仓行，请查看下方校验说明或换图重试。"
                _notify_brief(
                    "未识别到有效持仓行，请查看下方校验说明",
                    type_="warning",
                )
            else:
                status_label.text = f"识别完成，共 {n} 行；请核对下方表格与校验结果。"
                _notify_brief(f"识别完成，共 {n} 行", type_="positive")
        except Exception as e:
            status_label.text = f"识别失败：{e}"
            _notify_brief(str(e), type_="negative", ms=20000)
        else:
            path_done = uploaded_path.get("path")
            if path_done is not None and path_done.exists():
                try:
                    path_done.unlink()
                except OSError:
                    pass
            uploaded_path["path"] = None
        finally:
            extract_btn.props(remove="loading")
            extract_btn.enable()

    extract_btn = ui.button("识别仓位", on_click=do_extract, color="primary").classes("w-full q-mt-md")

    result_container = ui.column().classes("w-full q-mt-md")
    if _last_summary is not None:
        _render_position_result(_last_summary, result_container)
