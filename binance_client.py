import logging
import time
from typing import Callable, Optional, TypeVar

import pandas as pd
import requests
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL
from binance.exceptions import BinanceAPIException, BinanceRequestException

from config import (
    API_KEY,
    API_MAX_RETRIES,
    API_SECRET,
    INTERVAL,
    LEVERAGE,
    RECV_WINDOW_MS,
    SYMBOL,
    USE_TESTNET,
)

log = logging.getLogger(__name__)

T = TypeVar("T")

RETRYABLE_BINANCE_CODES = {
    -1000,  # UNKNOWN
    -1001,  # DISCONNECTED
    -1003,  # TOO_MANY_REQUESTS
    -1006,  # UNEXPECTED_RESP
    -1007,  # TIMEOUT
    -1021,  # INVALID_TIMESTAMP (clock drift)
    -1099,  # NOT_FOUND (sometimes transient)
}


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (requests.exceptions.RequestException, ConnectionError, TimeoutError)):
        return True
    if isinstance(exc, BinanceRequestException):
        return True
    if isinstance(exc, BinanceAPIException):
        return exc.code in RETRYABLE_BINANCE_CODES or exc.status_code in (408, 429, 500, 502, 503, 504)
    return False


def with_retry(fn: Callable[[], T], label: str = "api", max_attempts: int = API_MAX_RETRIES) -> T:
    delay = 1.0
    last_exc: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if not _is_retryable(e) or attempt == max_attempts:
                raise
            log.warning(f"{label}: attempt {attempt}/{max_attempts} failed ({e}), retry in {delay:.1f}s")
            time.sleep(delay)
            delay = min(delay * 2, 30.0)
    assert last_exc is not None
    raise last_exc


class Binance:
    def __init__(self):
        if not API_KEY or not API_SECRET:
            raise RuntimeError("BINANCE_API_KEY / BINANCE_API_SECRET not set")
        self.client = Client(API_KEY, API_SECRET, testnet=USE_TESTNET)
        self.price_tick: float = 0.1
        self.qty_step: float = 0.001
        self.min_qty: float = 0.001
        self._init_account()

    def _init_account(self) -> None:
        # Force one-way mode so position lookups are unambiguous.
        try:
            self.client.futures_change_position_mode(dualSidePosition=False, recvWindow=RECV_WINDOW_MS)
            log.info("position mode: ONE-WAY")
        except BinanceAPIException as e:
            # -4059 = "No need to change position side"
            if e.code != -4059:
                log.warning(f"set position mode: {e}")

        try:
            with_retry(
                lambda: self.client.futures_change_leverage(
                    symbol=SYMBOL, leverage=LEVERAGE, recvWindow=RECV_WINDOW_MS
                ),
                "set leverage",
            )
        except Exception as e:
            log.warning(f"set leverage failed: {e}")

        try:
            self.client.futures_change_margin_type(
                symbol=SYMBOL, marginType="ISOLATED", recvWindow=RECV_WINDOW_MS
            )
            log.info("margin type: ISOLATED")
        except BinanceAPIException as e:
            # -4046 = "No need to change margin type"
            if e.code != -4046:
                log.warning(f"set margin type: {e}")

        info = with_retry(lambda: self.client.futures_exchange_info(), "exchange info")
        for s in info["symbols"]:
            if s["symbol"] == SYMBOL:
                for f in s["filters"]:
                    if f["filterType"] == "PRICE_FILTER":
                        self.price_tick = float(f["tickSize"])
                    elif f["filterType"] == "LOT_SIZE":
                        self.qty_step = float(f["stepSize"])
                        self.min_qty = float(f["minQty"])
                break

    def klines(self, limit: int = 300) -> pd.DataFrame:
        data = with_retry(
            lambda: self.client.futures_klines(symbol=SYMBOL, interval=INTERVAL, limit=limit),
            "klines",
        )
        return pd.DataFrame(
            data,
            columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "qav", "trades", "tbbav", "tbqav", "ignore",
            ],
        )

    def _account(self) -> dict:
        return with_retry(
            lambda: self.client.futures_account(recvWindow=RECV_WINDOW_MS),
            "futures_account",
        )

    def equity_usdt(self) -> float:
        return float(self._account()["totalWalletBalance"])

    def available_usdt(self) -> float:
        return float(self._account()["availableBalance"])

    def mark_price(self) -> float:
        data = with_retry(lambda: self.client.futures_mark_price(symbol=SYMBOL), "mark_price")
        return float(data["markPrice"])

    def position(self) -> Optional[dict]:
        """Return the active position dict, or None. Raises on persistent API failure."""
        positions = with_retry(
            lambda: self.client.futures_position_information(
                symbol=SYMBOL, recvWindow=RECV_WINDOW_MS
            ),
            "position_information",
        )
        for p in positions:
            amt_raw = p.get("positionAmt", "0")
            try:
                if float(amt_raw) != 0:
                    return p
            except (TypeError, ValueError):
                log.warning(f"unparseable positionAmt: {amt_raw!r}")
                continue
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

        entry = with_retry(
            lambda: self.client.futures_create_order(
                symbol=SYMBOL,
                side=order_side,
                type="MARKET",
                quantity=qty,
                recvWindow=RECV_WINDOW_MS,
            ),
            "entry order",
        )

        with_retry(
            lambda: self.client.futures_create_order(
                symbol=SYMBOL,
                side=opp_side,
                type="STOP_MARKET",
                stopPrice=self.round_price(sl_price),
                closePosition=True,
                timeInForce="GTC",
                workingType="MARK_PRICE",
                recvWindow=RECV_WINDOW_MS,
            ),
            "SL order",
        )
        with_retry(
            lambda: self.client.futures_create_order(
                symbol=SYMBOL,
                side=opp_side,
                type="TAKE_PROFIT_MARKET",
                stopPrice=self.round_price(tp_price),
                closePosition=True,
                timeInForce="GTC",
                workingType="MARK_PRICE",
                recvWindow=RECV_WINDOW_MS,
            ),
            "TP order",
        )
        return entry

    def cancel_open_orders(self) -> None:
        try:
            with_retry(
                lambda: self.client.futures_cancel_all_open_orders(
                    symbol=SYMBOL, recvWindow=RECV_WINDOW_MS
                ),
                "cancel orders",
            )
        except Exception as e:
            log.warning(f"cancel orders failed: {e}")

    def close_position(self) -> None:
        pos = self.position()
        if not pos:
            return
        amt = float(pos["positionAmt"])
        side = SIDE_SELL if amt > 0 else SIDE_BUY
        with_retry(
            lambda: self.client.futures_create_order(
                symbol=SYMBOL,
                side=side,
                type="MARKET",
                quantity=abs(amt),
                reduceOnly=True,
                recvWindow=RECV_WINDOW_MS,
            ),
            "close position",
        )
        self.cancel_open_orders()
