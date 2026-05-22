#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Streamlit：做T净收益、涨跌幅↔目标价、两价算涨跌幅。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

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


def _css_signed_cell(x: object) -> str:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return ""
    if v > 0:
        return f"color: {_CN_RED}; font-weight: 600"
    if v < 0:
        return f"color: {_CN_GREEN}; font-weight: 600"
    return f"color: {_CN_GRAY}"


def _render_ashare_big_number(label: str, value_text: str, signed: float) -> None:
    c = _signed_color(signed)
    st.markdown(
        "<div style='margin:0.15rem 0 0.65rem 0'>"
        f"<div style='font-size:0.875rem;color:rgba(0,0,0,0.55);margin-bottom:0.2rem'>{label}</div>"
        f"<div style='font-size:1.85rem;font-weight:700;font-variant-numeric:tabular-nums;color:{c}'>{value_text}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# session_state keys
K_HIST_T = "hist_t_profit"
K_LAST_T = "last_t_profit"
K_HIST_P2PR = "hist_pct_to_price"
K_LAST_P2PR = "last_pct_to_price"
K_HIST_PR2P = "hist_price_to_pct"
K_LAST_PR2P = "last_price_to_pct"


def _now_str() -> str:
    return datetime.now().strftime("%m-%d %H:%M:%S")


def _init_session() -> None:
    defaults: dict[str, Any] = {
        K_HIST_T: [],
        K_LAST_T: None,
        K_HIST_P2PR: [],
        K_LAST_P2PR: None,
        K_HIST_PR2P: [],
        K_LAST_PR2P: None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _trim_hist(key: str) -> None:
    lst: list = st.session_state[key]
    if len(lst) > MAX_HISTORY:
        del lst[MAX_HISTORY:]


def _history_block(
    *,
    hist_key: str,
    last_key: str,
    clear_key: str,
    title: str = "历史记录",
    signed_columns: tuple[str, ...] = (),
) -> None:
    st.divider()
    hc, bc = st.columns([4, 1])
    with hc:
        st.subheader(title)
    with bc:
        if st.button("清除历史", key=clear_key):
            st.session_state[hist_key] = []
            st.session_state[last_key] = None
            st.rerun()

    rows: list = st.session_state[hist_key]
    if not rows:
        st.caption("暂无记录，点击上方「计算」后会自动记下。")
        return
    df = pd.DataFrame(rows)
    sty = df.style
    for col in signed_columns:
        if col in df.columns:
            sty = sty.map(_css_signed_cell, subset=[col])
    st.dataframe(sty, hide_index=True, width="stretch")


def _tab_t_profit() -> None:
    st.subheader("日内做T净收益")
    st.caption("万3 佣金（单笔最低 5 元）；个股含印花税与过户费，ETF 免收后两项。")

    c1, c2 = st.columns(2)
    with c1:
        trade_kind = st.radio("交易类型", ("个股", "ETF"), horizontal=True)
    with c2:
        order = st.radio("做T顺序", ("先卖后买", "先买后卖"), horizontal=True)

    trade_type = "stock" if trade_kind == "个股" else "etf"
    ia, ib = st.columns(2)
    if order == "先卖后买":
        with ia:
            first = st.number_input(
                "第一笔：卖出价（元）",
                min_value=0.0,
                value=10.0,
                step=0.01,
                format="%.4f",
                key="t_in_first",
            )
        with ib:
            second = st.number_input(
                "第二笔：买入价（元）",
                min_value=0.0,
                value=9.85,
                step=0.01,
                format="%.4f",
                key="t_in_second",
            )
        sell_price, buy_price = first, second
    else:
        with ia:
            first = st.number_input(
                "第一笔：买入价（元）",
                min_value=0.0,
                value=9.85,
                step=0.01,
                format="%.4f",
                key="t_in_first",
            )
        with ib:
            second = st.number_input(
                "第二笔：卖出价（元）",
                min_value=0.0,
                value=10.0,
                step=0.01,
                format="%.4f",
                key="t_in_second",
            )
        sell_price, buy_price = second, first

    shares = int(
        st.number_input("股数（股）", min_value=1, value=1000, step=100, key="t_shares")
    )

    if st.button("计算做T净收益", type="primary", key="btn_t"):
        b = compute_t_profit_breakdown(
            trade_type, sell_price, buy_price, shares, sequence_label=order
        )
        st.session_state[K_LAST_T] = b
        st.session_state[K_HIST_T].insert(
            0,
            {
                "时间": _now_str(),
                "类型": trade_kind,
                "顺序": order,
                "卖出价": round(b["sell_price"], 4),
                "买入价": round(b["buy_price"], 4),
                "股数": b["shares"],
                "毛利(元)": round(b["gross_profit"], 2),
                "手续费(元)": round(b["total_fee"], 2),
                "净收益(元)": round(b["net_profit"], 2),
            },
        )
        _trim_hist(K_HIST_T)

    last = st.session_state[K_LAST_T]
    if last is not None:
        b = last
        net = b["net_profit"]
        _render_ashare_big_number("净收益（元）", f"{net:,.2f}", net)

        with st.expander("明细", expanded=False):
            st.write(
                f"**卖出** {b['sell_price']:.4f} × {b['shares']} → 金额 **{b['sell_amount']:,.2f}** 元"
            )
            st.write(
                f"**买入** {b['buy_price']:.4f} × {b['shares']} → 金额 **{b['buy_amount']:,.2f}** 元"
            )
            gp = b["gross_profit"]
            gp_c = _signed_color(gp)
            st.markdown(
                f"**毛利** <span style='color:{gp_c};font-weight:600'>{gp:,.2f}</span> 元",
                unsafe_allow_html=True,
            )
            st.divider()
            st.write(
                f"卖出佣金 {b['sell_commission']:,.2f} 元　买入佣金 {b['buy_commission']:,.2f} 元"
            )
            tt = b["trade_type"]
            if tt == "stock":
                st.write(
                    f"印花税 {b['stamp_tax']:,.2f} 元　"
                    f"卖出过户 {b['sell_transfer']:,.2f} 元　买入过户 {b['buy_transfer']:,.2f} 元"
                )
            else:
                st.write("ETF：无印花税、过户费")
            st.write(f"**总手续费** {b['total_fee']:,.2f} 元")

    _history_block(
        hist_key=K_HIST_T,
        last_key=K_LAST_T,
        clear_key="clr_t",
        signed_columns=("毛利(元)", "净收益(元)"),
    )


def _tab_pct_to_price() -> None:
    st.subheader("涨跌幅 → 目标价")
    st.caption("高点回撤填**负**百分比；低点反弹填**正**百分比。")

    col_a, col_b = st.columns(2)
    with col_a:
        initial = st.number_input(
            "基准价（元）",
            min_value=0.0,
            value=100.0,
            step=0.01,
            format="%.4f",
            key="p2pr_initial",
        )
    with col_b:
        pct = st.number_input(
            "相对基准涨跌幅（%）",
            value=-5.0,
            step=0.1,
            format="%.4f",
            key="p2pr_pct",
        )

    if st.button("计算目标价", type="primary", key="btn_pct2p"):
        if initial < 0:
            st.error("基准价不能为负数。")
        else:
            new_price = price_after_change(initial, pct)
            if pct > 0:
                hint = "从基准向上（如低点反弹）"
            elif pct < 0:
                hint = "从基准向下（如高点回撤）"
            else:
                hint = "无变动"
            st.session_state[K_LAST_P2PR] = {
                "initial": initial,
                "pct": pct,
                "new_price": new_price,
                "hint": hint,
            }
            st.session_state[K_HIST_P2PR].insert(
                0,
                {
                    "时间": _now_str(),
                    "基准价": round(initial, 4),
                    "涨跌幅(%)": round(pct, 4),
                    "目标价": round(new_price, 4),
                    "说明": hint,
                },
            )
            _trim_hist(K_HIST_P2PR)

    last = st.session_state[K_LAST_P2PR]
    if last is not None:
        p = float(last["pct"])
        _render_ashare_big_number("目标价（元）", f"{last['new_price']:.4f}", p)
        st.caption(f"{p:+.4f}% · {last['hint']}")

    _history_block(
        hist_key=K_HIST_P2PR,
        last_key=K_LAST_P2PR,
        clear_key="clr_p2pr",
        signed_columns=("涨跌幅(%)",),
    )


def _tab_price_to_pct() -> None:
    st.subheader("两价 → 涨跌幅")
    st.caption("结束价相对起始价的涨跌百分比（涨为正、跌为负）。")

    col_s, col_e = st.columns(2)
    with col_s:
        start = st.number_input(
            "起始价（元）",
            min_value=0.0,
            value=10.0,
            step=0.01,
            format="%.4f",
            key="p2p_start",
        )
    with col_e:
        end = st.number_input(
            "结束价（元）",
            min_value=0.0,
            value=10.5,
            step=0.01,
            format="%.4f",
            key="p2p_end",
        )

    if st.button("计算涨跌幅", type="primary", key="btn_p2pct"):
        if start < 0:
            st.error("起始价不能为负数。")
        elif start == 0:
            st.error("起始价为 0 时无法计算百分比。")
        else:
            pct = pct_change_from_prices(start, end)
            if pct > 0:
                label = "上涨"
            elif pct < 0:
                label = "下跌"
            else:
                label = "持平"
            st.session_state[K_LAST_PR2P] = {
                "start": start,
                "end": end,
                "pct": pct,
                "label": label,
            }
            st.session_state[K_HIST_PR2P].insert(
                0,
                {
                    "时间": _now_str(),
                    "起始价": round(start, 4),
                    "结束价": round(end, 4),
                    "涨跌幅(%)": round(pct, 4),
                    "涨跌": label,
                },
            )
            _trim_hist(K_HIST_PR2P)

    last = st.session_state[K_LAST_PR2P]
    if last is not None:
        p = float(last["pct"])
        _render_ashare_big_number("相对涨跌幅（%）", f"{p:+.4f}%", p)
        st.caption(last["label"])

    _history_block(
        hist_key=K_HIST_PR2P,
        last_key=K_LAST_PR2P,
        clear_key="clr_pr2p",
        signed_columns=("涨跌幅(%)",),
    )


def render() -> None:
    _init_session()

    st.subheader("交易计算器")
    st.caption("做T净收益 · 按涨跌幅推算价格 · 两价算涨跌幅")

    tab1, tab2, tab3 = st.tabs(["做T净收益", "涨跌幅 → 目标价", "两价 → 涨跌幅"])
    with tab1:
        _tab_t_profit()
    with tab2:
        _tab_pct_to_price()
    with tab3:
        _tab_price_to_pct()
