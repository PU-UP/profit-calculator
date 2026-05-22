#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交易小算盘：profit_calc 计算器 + position_table 仓位占比。"""

from __future__ import annotations

import streamlit as st

from profit_calc import position_ui, ui


def main() -> None:
    st.set_page_config(page_title="交易小算盘", layout="centered")

    st.title("交易小算盘")

    tab_calc, tab_pos = st.tabs(["profit_calc", "position_table"])
    with tab_calc:
        ui.render()
    with tab_pos:
        position_ui.render()


if __name__ == "__main__":
    main()
