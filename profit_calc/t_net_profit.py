#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""日内做T：两腿成交后的净收益（含佣金、印花税、过户费等）。"""


def compute_t_profit_breakdown(trade_type, sell_price, buy_price, shares, *, sequence_label):
    """
    计算做T明细（卖出腿、买入腿各一笔；印花税等按卖出金额计）。
    :return: dict，供 CLI 打印或 Streamlit 展示
    """
    sell_amount = sell_price * shares
    buy_amount = buy_price * shares
    gross_profit = sell_amount - buy_amount

    def calc_commission(amount):
        commission = amount * 0.0003
        return max(commission, 5.0)

    sell_commission = calc_commission(sell_amount)
    buy_commission = calc_commission(buy_amount)

    sell_transfer = 0.0
    buy_transfer = 0.0
    if trade_type == 'stock':
        sell_transfer = sell_amount * 0.00001
        buy_transfer = buy_amount * 0.00001

    stamp_tax = 0.0
    if trade_type == 'stock':
        stamp_tax = sell_amount * 0.0005

    total_fee = sell_commission + buy_commission + sell_transfer + buy_transfer + stamp_tax
    net_profit = gross_profit - total_fee

    return {
        "trade_type": trade_type,
        "sequence_label": sequence_label,
        "sell_price": sell_price,
        "buy_price": buy_price,
        "shares": shares,
        "sell_amount": sell_amount,
        "buy_amount": buy_amount,
        "gross_profit": gross_profit,
        "sell_commission": sell_commission,
        "buy_commission": buy_commission,
        "sell_transfer": sell_transfer,
        "buy_transfer": buy_transfer,
        "stamp_tax": stamp_tax,
        "total_fee": total_fee,
        "net_profit": net_profit,
    }


def calculate_t_profit(trade_type, sell_price, buy_price, shares, *, sequence_label):
    """
    计算做T的净收益（卖出腿、买入腿各一笔，与先后无关；印花税等按卖出金额计）
    :param trade_type: 'stock' 或 'etf'
    :param sell_price: 卖出成交价（元）
    :param buy_price:  买入成交价（元）
    :param shares:     股数（份数）
    :param sequence_label: 展示用，如「先卖后买」「先买后卖」
    :return: 净收益（元）
    """
    b = compute_t_profit_breakdown(
        trade_type, sell_price, buy_price, shares, sequence_label=sequence_label
    )
    tt = b["trade_type"]

    print("\n========== 做T净收益 ==========")
    print(f"交易类型：{'个股' if tt == 'stock' else 'ETF'}")
    print(f"做T顺序：{b['sequence_label']}")
    print(f"卖出价：{b['sell_price']:.2f} 元  买入价：{b['buy_price']:.2f} 元  股数：{b['shares']} 股")
    print(f"卖出金额：{b['sell_amount']:.2f} 元  买入金额：{b['buy_amount']:.2f} 元")
    print(f"毛利：{b['gross_profit']:.2f} 元\n")

    print("【费用明细】")
    print(f"卖出佣金：{b['sell_commission']:.2f} 元 (万3, 最低5元)")
    print(f"买入佣金：{b['buy_commission']:.2f} 元 (万3, 最低5元)")
    if tt == 'stock':
        print(f"卖出印花税：{b['stamp_tax']:.2f} 元 (0.05%)")
        print(f"卖出过户费：{b['sell_transfer']:.2f} 元 (0.001%)")
        print(f"买入过户费：{b['buy_transfer']:.2f} 元 (0.001%)")
    else:
        print("ETF免收印花税、过户费")
    print(f"总手续费：{b['total_fee']:.2f} 元\n")

    print(f"净收益：{b['net_profit']:.2f} 元")
    print("==============================\n")
    return b["net_profit"]


def main():
    print("请输入交易信息：")
    while True:
        trade_type = input("交易类型（输入 stock 或 etf）：").strip().lower()
        if trade_type in ('stock', 'etf'):
            break
        print("输入无效，请输入 'stock' 或 'etf'")

    while True:
        order = input("做T顺序（1=先卖后买，2=先买后卖）：").strip()
        if order == "1":
            sequence_label = "先卖后买"
            break
        if order == "2":
            sequence_label = "先买后卖"
            break
        print("请输入 1 或 2")

    try:
        first = float(input("第一笔成交价格（元）："))
        second = float(input("第二笔成交价格（元）："))
        shares = int(input("股数（股）："))
    except ValueError:
        print("价格或股数输入错误，请确保为数字。")
        return

    if sequence_label == "先卖后买":
        sell_price, buy_price = first, second
    else:
        sell_price, buy_price = second, first

    calculate_t_profit(trade_type, sell_price, buy_price, shares, sequence_label=sequence_label)


if __name__ == "__main__":
    main()
