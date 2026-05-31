#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Streamlit：上传持仓截图，展示各标的金额与占比。"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from profit_calc.position_extract import describe_recognition_backend, extract_holdings_from_image

K_POS_RESULT = "position_table_result"


def render() -> None:
    st.subheader("仓位占比")
    st.caption(
        "以截图顶栏「账户资产」为总资产；各证券占比为市值/账户资产；"
        "浮动盈亏与比例为截图持仓行识别值；"
        "剩余资金 = 账户资产 − 总市值（不采用易混淆的「可用」识别值）。"
    )

    with st.sidebar:
        st.caption("高级")
        timeout_vision = st.number_input(
            "vision 超时（秒）",
            min_value=30,
            max_value=300,
            value=120,
            step=10,
            key="pos_timeout_vision",
        )
        timeout_text = st.number_input(
            "text 超时（秒）",
            min_value=30,
            max_value=300,
            value=120,
            step=10,
            key="pos_timeout_text",
        )
        with st.expander("识别环境", expanded=False):
            for label, value in describe_recognition_backend().items():
                st.caption(f"{label}：{value}")

    uploaded = st.file_uploader(
        "持仓截图",
        type=["png", "jpg", "jpeg", "webp"],
        key="pos_image_upload",
    )

    if st.button("识别仓位", type="primary", key="btn_pos_extract", disabled=uploaded is None):
        if uploaded is None:
            st.warning("请先上传截图。")
            return

        suffix = Path(uploaded.name).suffix or ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = Path(tmp.name)

        try:
            with st.spinner("正在识别截图（vision + 解析）…"):
                summary = extract_holdings_from_image(
                    tmp_path,
                    timeout_vision=int(timeout_vision),
                    timeout_text=int(timeout_text),
                )
            st.session_state[K_POS_RESULT] = summary
        except Exception as e:
            st.error(str(e))
            with st.expander("识别环境（出错时）", expanded=True):
                for label, value in describe_recognition_backend().items():
                    st.write(f"**{label}**：{value}")
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    result = st.session_state.get(K_POS_RESULT)
    if result is None:
        st.info("上传截图后点击「识别仓位」。")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("账户资产（元）", f"{result.account_assets:,.2f}")
    with c2:
        st.metric("总市值（元）", f"{result.market_value:,.2f}")
    with c3:
        st.metric("剩余资金（元）", f"{result.cash:,.2f}", help="账户资产 − 总市值")

    df: pd.DataFrame = result.df
    if df.empty:
        st.warning("未识别到有效持仓行，请换图或重试。")
    else:
        fmt: dict[str, str] = {"金额（元）": "{:,.2f}", "占比（%）": "{:.1f}%"}
        if "浮动盈亏（元）" in df.columns:
            fmt["浮动盈亏（元）"] = "{:+,.2f}"
        if "浮动比例（%）" in df.columns:
            fmt["浮动比例（%）"] = "{:+.2f}%"
        styled = df.style.format(fmt, na_rep="—")
        st.dataframe(styled, hide_index=True, width="stretch")

    expand_diag = df.empty or any(c.startswith("⚠") for c in result.checks)
    with st.expander("识别诊断", expanded=expand_diag):
        st.write(f"**识别后端**：{result.backend or '—'}")
        st.write(f"**后端选择**：{result.backend_mode or '—'}")
        st.write(f"**MINIMAX_REGION**：{result.region or '—'}")
        st.write(f"**API Key**：{result.api_key_hint or '—'}")
        st.write(f"**Vision API**：{result.vision_api or '—'}")
        st.write(f"**Vision 转写字数**：{result.transcript_chars}")
        if result.transcript_preview and (df.empty or result.transcript_chars < 120):
            st.write(f"**Vision 转写预览**：{result.transcript_preview}")
        st.write(f"**模型返回 holdings 条数**：{result.holdings_raw_count}")
        st.write(f"**有效持仓行数**：{len(result.df)}")
        if result.checks:
            st.markdown("**校验结果**")
            for line in result.checks:
                st.write(line)

    st.caption("数据来自截图识别，请核对；占比分母为账户资产，非总市值。")
