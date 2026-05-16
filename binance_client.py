import logging
from typing import Optional

import pandas as pd
from binance.client import Client
from binance.enums import (
    ORDER_TYPE_MARKET,
    ORDER_TYPE_STOP_MARKET,
    ORDER_TYPE_TAKE_PROFIT_MARKET,
    SIDE_BUY,
    SIDE_SELL,
)

from config import API_KEY, API_SECRET, INTERVAL, LEVERAGE, SYMBOL, USE_TESTNET

log = logging.getLogger(__name__)


class Binance:
    def __init__(self):
        if not API_KEY or not API_SECRET:
            raise RuntimeError("BINANCE_API_KEY / BINANCE_API_SECRET not set in .env")
        self.client = Client(API_KEY, API_SECRET, testnet=USE_TESTNET)
        self.price_tick: float = 0.1
        self.qty_step: float = 0.001
        self.min_qty: float = 0.001
        self._init_symbol()

    def _init_symbol(self) -> None:
        try:
            self.client.futures_change_leverage(symbol=SYMBOL, leverage=LEVERAGE)
        except Exception as e:
            log.warning(f"set leverage failed: {e}")
        try:
            self.client.futures_change_margin_type(symbol=SYMBOL, marginType="ISOLATED")
        except Exception as e:
            log.debug(f"set margin type: {e}")

        info = self.client.futures_exchange_info()
        for s in info["symbols"]:
            if s["symbol"] == SYMBOL:
                for f in s["filters"]:
                    if f["filterType"] == "PRICE_FILTER":
                        self.price_tick = float(f["tickSize"])
                    elif f["filterType"] == "LOT_SIZE":
                        self.qty_step = float(f["stepSize"])
                        self.min_qty = float(f["minQty"])
                break

    def klines(self, limit: int = 100) -> pd.DataFrame:
        data = self.client.futures_klines(symbol=SYMBOL, interval=INTERVAL, limit=limit)
        df = pd.DataFrame(
            data,
            columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "qav", "trades", "tbbav", "tbqav", "ignore",
            ],
        )
        return df

    def equity_usdt(self) -> float:
        acct = self.client.futures_account()
        return float(acct["totalWalletBalance"])

    def available_usdt(self) -> float:
        acct = self.client.futures_account()
        return float(acct["availableBalance"])

    def mark_price(self) -> float:
        return float(self.client.futures_mark_price(symbol=SYMBOL)["markPrice"])

    def position(self) -> Optional[dict]:
        positions = self.client.futures_position_information(symbol=SYMBOL)
        for p in positions:
            if float(p["positionAmt"]) != 0:
                return p
        return None

    def round_qty(self, qty: float) -> float:
        step = self.qty_step
        return float(int(qty / step) * step)

    def round_price(self, price: float) -> float:
        tick = self.price_tick
        return float(int(price / tick) * tick)

    def open_position(self, side: str, qty: float, sl_price: float, tp_price: float) -> dict:
        order_side = SIDE_BUY if side == "LONG" else SIDE_SELL
        opp_side = SIDE_SELL if side == "LONG" else SIDE_BUY

        entry = self.client.futures_create_order(
            symbol=SYMBOL,
            side=order_side,
            type=ORDER_TYPE_MARKET,
            quantity=qty,
        )

        self.client.futures_create_order(
            symbol=SYMBOL,
            side=opp_side,
            type=ORDER_TYPE_STOP_MARKET,
            stopPrice=self.round_price(sl_price),
            closePosition=True,
            timeInForce="GTC",
            workingType="MARK_PRICE",
        )
        self.client.futures_create_order(
            symbol=SYMBOL,
            side=opp_side,
            type=ORDER_TYPE_TAKE_PROFIT_MARKET,
            stopPrice=self.round_price(tp_price),
            closePosition=True,
            timeInForce="GTC",
            workingType="MARK_PRICE",
        )
        return entry

    def cancel_open_orders(self) -> None:
        try:
            self.client.futures_cancel_all_open_orders(symbol=SYMBOL)
        except Exception as e:
            log.warning(f"cancel orders failed: {e}")

    def close_position(self) -> None:
        pos = self.position()
        if not pos:
            return
        amt = float(pos["positionAmt"])
        side = SIDE_SELL if amt > 0 else SIDE_BUY
        self.client.futures_create_order(
            symbol=SYMBOL,
            side=side,
            type=ORDER_TYPE_MARKET,
            quantity=abs(amt),
            reduceOnly=True,
        )
        self.cancel_open_orders()
