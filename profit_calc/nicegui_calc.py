#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NiceGUI：做T净收益、涨跌幅↔目标价、两价算涨跌幅。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from nicegui import ui

from profit_calc.pct_to_price import price_after_change
from profit_calc.price_to_pct import pct_change_from_prices
from profit_calc.t_net_profit import compute_t_profit_breakdown

MAX_HISTORY = 100

# A 股看盘习惯：涨/多为红，跌/空为绿
_CN_RED = "#c62828"
_CN_GREEN = "#2e7d32"
_CN_GRAY = "#757575"


def _signed_color(v: float) -> str:
    if v > 0:
        return _CN_RED
    if v < 0:
        return _CN_GREEN
    return _CN_GRAY


def _now_str() -> str:
    return datetime.now().strftime("%m-%d %H:%M:%S")


def _big_number(label: str, value_text: str, signed: float) -> None:
    """A股风格大数字展示：红涨绿跌。"""
    c = _signed_color(signed)
    ui.html(
        f"<div style='margin:0.15rem 0 0.65rem 0'>"
        f"<div style='font-size:0.875rem;color:rgba(0,0,0,0.55);margin-bottom:0.2rem'>{label}</div>"
        f"<div style='font-size:1.85rem;font-weight:700;font-variant-numeric:tabular-nums;color:{c}'>{value_text}</div>"
        f"</div>"
    )


def _render_t_detail(b: dict) -> None:
    """渲染做T净收益结果明细（在当前容器内）。"""
    net = b["net_profit"]
    _big_number("净收益（元）", f"{net:,.2f}", net)

    with ui.expansion("明细", icon="info").classes("w-full"):
        ui.label(f"卖出 {b['sell_price']:.4f} × {b['shares']} → 金额 {b['sell_amount']:,.2f} 元")
        ui.label(f"买入 {b['buy_price']:.4f} × {b['shares']} → 金额 {b['buy_amount']:,.2f} 元")
        gp = b["gross_profit"]
        gp_c = _signed_color(gp)
        ui.html(f"<b>毛利</b> <span style='color:{gp_c};font-weight:600'>{gp:,.2f}</span> 元")
        ui.separator()
        ui.label(f"卖出佣金 {b['sell_commission']:,.2f} 元　买入佣金 {b['buy_commission']:,.2f} 元")
        if b["trade_type"] == "stock":
            ui.label(f"印花税 {b['stamp_tax']:,.2f} 元　卖出过户 {b['sell_transfer']:,.2f} 元　买入过户 {b['buy_transfer']:,.2f} 元")
        else:
            ui.label("ETF：无印花税、过户费")
        ui.label(f"总手续费 {b['total_fee']:,.2f} 元")


# ── 做T净收益 ────────────────────────────────────────────────────

def _tab_t_profit(history: list[dict]) -> None:
    ui.label("日内做T净收益").classes("text-subtitle1 font-bold")
    ui.label("万3 佣金（单笔最低 5 元）；个股含印花税与过户费，ETF 免收后两项。").classes("text-caption")

    with ui.row().classes("w-full gap-4"):
        trade_kind = ui.select({"stock": "个股", "etf": "ETF"}, value="stock", label="交易类型").classes("flex-1")
        order = ui.select({"sell_first": "先卖后买", "buy_first": "先买后卖"}, value="sell_first", label="做T顺序").classes("flex-1")

    with ui.row().classes("w-full gap-4"):
        first_price = ui.number(value=10.0, label="第一笔价格（元）", format="%.4f", step=0.01).classes("flex-1")
        second_price = ui.number(value=9.85, label="第二笔价格（元）", format="%.4f", step=0.01).classes("flex-1")

    shares = ui.number(value=1000, label="股数（股）", step=100, min=1).classes("w-full")

    result_container = ui.column().classes("w-full")

    def compute():
        trade_type = trade_kind.value
        order_val = order.value
        fp = first_price.value
        sp = second_price.value
        sh = int(shares.value)

        if order_val == "sell_first":
            sell_p, buy_p = fp, sp
            seq_label = "先卖后买"
        else:
            sell_p, buy_p = sp, fp
            seq_label = "先买后卖"

        b = compute_t_profit_breakdown(trade_type, sell_p, buy_p, sh, sequence_label=seq_label)

        history.insert(0, {
            "时间": _now_str(),
            "类型": "个股" if trade_type == "stock" else "ETF",
            "顺序": "先卖后买" if order_val == "sell_first" else "先买后卖",
            "卖出价": round(b["sell_price"], 4),
            "买入价": round(b["buy_price"], 4),
            "股数": b["shares"],
            "毛利(元)": round(b["gross_profit"], 2),
            "手续费(元)": round(b["total_fee"], 2),
            "净收益(元)": round(b["net_profit"], 2),
        })
        if len(history) > MAX_HISTORY:
            del history[MAX_HISTORY:]

        result_container.clear()
        with result_container:
            _render_t_detail(b)
        refresh_history()

    ui.button("计算做T净收益", on_click=compute, color="primary").classes("w-full")

    hist_container = ui.column().classes("w-full")

    def refresh_history() -> None:
        _bind_history_panel(history, "做T净收益历史", hist_container)

    refresh_history()


# ── 涨跌幅 → 目标价 ──────────────────────────────────────────────

def _tab_pct_to_price(history: list[dict]) -> None:
    ui.label("涨跌幅 → 目标价").classes("text-subtitle1 font-bold")
    ui.label("高点回撤填负百分比；低点反弹填正百分比。").classes("text-caption")

    with ui.row().classes("w-full gap-4"):
        initial = ui.number(value=100.0, label="基准价（元）", format="%.4f", step=0.01).classes("flex-1")
        pct = ui.number(value=-5.0, label="相对基准涨跌幅（%）", format="%.4f", step=0.1).classes("flex-1")

    result_container = ui.column().classes("w-full")

    def compute():
        ini = initial.value
        p = pct.value
        if ini < 0:
            ui.notify("基准价不能为负数", type="warning")
            return
        new_price = price_after_change(ini, p)
        if p > 0:
            hint = "从基准向上（如低点反弹）"
        elif p < 0:
            hint = "从基准向下（如高点回撤）"
        else:
            hint = "无变动"

        history.insert(0, {
            "时间": _now_str(),
            "基准价": round(ini, 4),
            "涨跌幅(%)": round(p, 4),
            "目标价": round(new_price, 4),
            "说明": hint,
        })
        if len(history) > MAX_HISTORY:
            del history[MAX_HISTORY:]

        result_container.clear()
        with result_container:
            _big_number("目标价（元）", f"{new_price:.4f}", p)
            ui.label(f"{p:+.4f}% · {hint}").classes("text-caption")
        refresh_history()

    ui.button("计算目标价", on_click=compute, color="primary").classes("w-full")

    hist_container = ui.column().classes("w-full")

    def refresh_history() -> None:
        _bind_history_panel(history, "涨跌幅→目标价历史", hist_container)

    refresh_history()


# ── 两价 → 涨跌幅 ────────────────────────────────────────────────

def _tab_price_to_pct(history: list[dict]) -> None:
    ui.label("两价 → 涨跌幅").classes("text-subtitle1 font-bold")
    ui.label("结束价相对起始价的涨跌百分比（涨为正、跌为负）。").classes("text-caption")

    with ui.row().classes("w-full gap-4"):
        start = ui.number(value=10.0, label="起始价（元）", format="%.4f", step=0.01).classes("flex-1")
        end = ui.number(value=10.5, label="结束价（元）", format="%.4f", step=0.01).classes("flex-1")

    result_container = ui.column().classes("w-full")

    def compute():
        s = start.value
        e = end.value
        if s < 0:
            ui.notify("起始价不能为负数", type="warning")
            return
        if s == 0:
            ui.notify("起始价为 0 时无法计算百分比", type="warning")
            return
        p = pct_change_from_prices(s, e)
        if p > 0:
            label = "上涨"
        elif p < 0:
            label = "下跌"
        else:
            label = "持平"

        history.insert(0, {
            "时间": _now_str(),
            "起始价": round(s, 4),
            "结束价": round(e, 4),
            "涨跌幅(%)": round(p, 4),
            "涨跌": label,
        })
        if len(history) > MAX_HISTORY:
            del history[MAX_HISTORY:]

        result_container.clear()
        with result_container:
            _big_number("相对涨跌幅（%）", f"{p:+.4f}%", p)
            ui.label(label).classes("text-caption")
        refresh_history()

    ui.button("计算涨跌幅", on_click=compute, color="primary").classes("w-full")

    hist_container = ui.column().classes("w-full")

    def refresh_history() -> None:
        _bind_history_panel(history, "两价→涨跌幅历史", hist_container)

    refresh_history()


def _bind_history_panel(history: list[dict], title: str, container) -> None:
    """绑定可刷新的历史记录区。"""

    def refresh() -> None:
        container.clear()
        with container:

            def on_clear() -> None:
                history.clear()
                refresh()

            _render_history(history, title, on_clear)

    refresh()


# ── 历史记录 ─────────────────────────────────────────────────────

def _render_history(history: list[dict], title: str, on_clear) -> None:
    """在容器内绘制历史区（由外层 clear + 重绘刷新）。"""
    ui.separator()
    with ui.row().classes("w-full items-center justify-between"):
        ui.label(title).classes("text-subtitle2 font-bold")
        ui.button("清除历史", on_click=on_clear, color="grey").props("dense")

    if not history:
        ui.label("暂无记录，点击上方「计算」后会自动记下。").classes("text-caption")
        return

    columns = [
        {"name": k, "label": k, "field": k, "align": "right" if i > 0 else "left", "sortable": False}
        for i, k in enumerate(history[0].keys())
    ]
    rows = [{**row, "_id": f"{row.get('时间', '')}-{i}"} for i, row in enumerate(history[:20])]

    ui.table(
        columns=columns,
        rows=rows,
        row_key="_id",
    ).classes("w-full").props("flat dense virtual-scroll")


# ── 渲染入口 ─────────────────────────────────────────────────────

def render(
    hist_t: list[dict],
    hist_p2pr: list[dict],
    hist_pr2p: list[dict],
) -> None:
    """渲染交易计算器主界面。历史列表由 app.storage.user 传入并在计算后刷新表格。"""
    ui.label("交易计算器").classes("text-h6 font-bold")
    ui.label("做T净收益 · 按涨跌幅推算价格 · 两价算涨跌幅").classes("text-caption q-mb-md")

    with ui.tabs().classes("w-full") as tabs:
        ui.tab("t_profit", label="做T净收益", icon="swap_vert")
        ui.tab("pct_to_price", label="涨跌幅→目标价", icon="trending_up")
        ui.tab("price_to_pct", label="两价→涨跌幅", icon="percent")

    with ui.tab_panels(tabs, value="t_profit").classes("w-full"):
        with ui.tab_panel("t_profit"):
            _tab_t_profit(hist_t)

        with ui.tab_panel("pct_to_price"):
            _tab_pct_to_price(hist_p2pr)

        with ui.tab_panel("price_to_pct"):
            _tab_price_to_pct(hist_pr2p)
