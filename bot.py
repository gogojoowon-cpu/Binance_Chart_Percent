import logging
import sys
import time

from binance_client import Binance
from config import (
    ATR_PERIOD,
    ATR_SL_MULT,
    ATR_TP_MULT,
    DAILY_LOSS_LIMIT,
    DAILY_ROI_TARGET,
    KLINES_LIMIT,
    LEVERAGE,
    LIVE_TRADING,
    MARGIN_PCT,
    MAX_SL_PCT,
    MIN_SL_PCT,
    POLL_INTERVAL_SEC,
    SYMBOL,
    USE_TESTNET,
)
from indicators import atr as atr_fn
from risk_manager import DailyRiskManager
from strategy import decide

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("bot")


def compute_qty(equity: float, available: float, price: float) -> float:
    # Margin per entry compounds: as equity grows, this grows too.
    margin = min(available, equity * MARGIN_PCT)
    notional = margin * LEVERAGE
    return notional / price


def main() -> None:
    log.info("=== Binance BTC Futures Auto-Trading Bot ===")
    log.info(f"LIVE_TRADING={LIVE_TRADING}  USE_TESTNET={USE_TESTNET}")
    log.info(f"Symbol={SYMBOL}  Leverage={LEVERAGE}x  Margin per entry={MARGIN_PCT*100:.0f}%")
    log.info(f"SL=ATR*{ATR_SL_MULT} (floor {MIN_SL_PCT*100:.2f}%, cap {MAX_SL_PCT*100:.2f}%)  TP=ATR*{ATR_TP_MULT}  R:R=1:{ATR_TP_MULT/ATR_SL_MULT:.1f}")
    log.info(f"Daily target={DAILY_ROI_TARGET*100:.0f}%  Daily loss cap={DAILY_LOSS_LIMIT*100:.0f}%")

    if not LIVE_TRADING:
        log.warning("DRY RUN MODE — no real orders. Set LIVE_TRADING=true in env to enable.")

    api = Binance()
    risk = DailyRiskManager(DAILY_ROI_TARGET, DAILY_LOSS_LIMIT)

    while True:
        try:
            equity = api.equity_usdt()
            risk.update(equity)

            stop, reason = risk.should_stop(equity)
            if stop:
                pos = api.position()
                if pos and LIVE_TRADING:
                    log.info(f"{reason} → closing open position")
                    api.close_position()
                log.info(f"{reason} → idle 5 min")
                time.sleep(300)
                continue

            pos = api.position()
            if pos is not None:
                amt = float(pos["positionAmt"])
                upnl = float(pos["unRealizedProfit"])
                log.info(
                    f"holding amt={amt}  uPnL={upnl:+.2f}  equity={equity:.2f}  dayROI={risk.roi(equity)*100:+.2f}%"
                )
                time.sleep(POLL_INTERVAL_SEC)
                continue

            df = api.klines(limit=KLINES_LIMIT)
            signal = decide(df)
            log.info(
                f"signal={signal}  equity={equity:.2f}  dayROI={risk.roi(equity)*100:+.2f}%"
            )

            if signal is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue

            price = api.mark_price()
            available = api.available_usdt()
            qty = api.round_qty(compute_qty(equity, available, price))
            if qty < api.min_qty:
                log.warning(f"qty {qty} below min {api.min_qty} — skipping entry")
                time.sleep(POLL_INTERVAL_SEC)
                continue

            last_atr = float(
                atr_fn(
                    df["high"].astype(float),
                    df["low"].astype(float),
                    df["close"].astype(float),
                    ATR_PERIOD,
                ).iloc[-1]
            )
            sl_dist_raw = last_atr * ATR_SL_MULT
            sl_dist = min(max(sl_dist_raw, price * MIN_SL_PCT), price * MAX_SL_PCT)
            tp_dist = sl_dist * (ATR_TP_MULT / ATR_SL_MULT)  # keep R:R constant after clipping

            if signal == "LONG":
                sl = price - sl_dist
                tp = price + tp_dist
            else:
                sl = price + sl_dist
                tp = price - tp_dist

            # Belt-and-suspenders: re-verify no position right before sending the order.
            # Protects against the "transient API blip → false None" double-entry case.
            recheck = api.position()
            if recheck is not None:
                log.warning("position appeared between check and entry — aborting this entry")
                time.sleep(POLL_INTERVAL_SEC)
                continue

            log.info(
                f"OPEN {signal}  qty={qty}  entry≈{price:.2f}  "
                f"SL={sl:.2f} ({sl_dist/price*100:.2f}%)  TP={tp:.2f} ({tp_dist/price*100:.2f}%)  "
                f"ATR={last_atr:.2f}"
            )

            if LIVE_TRADING:
                api.cancel_open_orders()
                api.open_position(signal, qty, sl, tp)
            else:
                log.info("(dry run — order not sent)")

            # Give the API state a moment to reflect the new position.
            time.sleep(POLL_INTERVAL_SEC)

        except KeyboardInterrupt:
            log.info("interrupted, exiting")
            sys.exit(0)
        except Exception as e:
            log.exception(f"loop error: {e}")
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
