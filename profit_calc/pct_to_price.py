#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""已知相对涨跌幅(%)，推算目标价。典型用法：高点回撤填负%、低点反弹填正%。"""


def price_after_change(initial_price, pct_change):
    """
    按涨跌幅计算变动后的价格。
    :param initial_price: 基准价（元），阶段高点或阶段低点
    :param pct_change: 相对基准的百分比：负数为从高点回撤，正数为从低点反弹
    :return: 变动后价格
    """
    return initial_price * (1 + pct_change / 100.0)


def main():
    print("【涨跌幅 → 目标价】高点回撤用负数，低点反弹用正数。")
    print("示例：高点 100，回撤 5% → 基准 100、涨跌幅 -5；低点 10，涨 8% → 基准 10、涨跌幅 8。\n")
    try:
        initial = float(input("基准价（元，阶段高点或阶段低点）："))
        pct = float(input("相对基准的涨跌幅（%）："))
    except ValueError:
        print("输入无效，请输入数字。")
        return

    if initial < 0:
        print("基准价不应为负数。")
        return

    new_price = price_after_change(initial, pct)

    if pct > 0:
        scenario = "从基准向上（如：低点反弹）"
    elif pct < 0:
        scenario = "从基准向下（如：高点回撤）"
    else:
        scenario = "无变动"

    print("\n========== 涨跌幅 → 目标价 ==========")
    print(f"基准价：{initial:.4f} 元")
    print(f"变动：{pct:+.2f}% — {scenario}")
    print(f"目标价：{new_price:.4f} 元")
    print("====================================\n")


if __name__ == "__main__":
    main()
