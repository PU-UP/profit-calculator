#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""已知起始价与结束价，计算相对涨跌幅(%)：涨为正、跌为负。"""


def pct_change_from_prices(start_price, end_price):
    """
    从起始价到结束价的相对涨跌幅（%）。
    :param start_price: 起始价（元），作分母
    :param end_price: 结束价（元）
    :return: 百分比，涨为正、跌为负
    """
    return (end_price - start_price) / start_price * 100.0


def main():
    print("【两价 → 涨跌幅】结束价相对起始价的涨跌百分比（涨为正、跌为负）。\n")
    try:
        start = float(input("起始价（元）："))
        end = float(input("结束价（元）："))
    except ValueError:
        print("输入无效，请输入数字。")
        return

    if start < 0:
        print("起始价不应为负数。")
        return
    if start == 0:
        print("起始价为 0 时无法计算百分比。")
        return

    pct = pct_change_from_prices(start, end)
    if pct > 0:
        label = "上涨"
    elif pct < 0:
        label = "下跌"
    else:
        label = "持平"

    print("\n========== 两价 → 涨跌幅 ==========")
    print(f"起始价：{start:.4f} 元  →  结束价：{end:.4f} 元")
    print(f"相对涨跌：{pct:+.4f}%（{label}）")
    print("==================================\n")


if __name__ == "__main__":
    main()
