import logging
import sys
import time

from binance_client import Binance
from config import (
    DAILY_LOSS_LIMIT,
    DAILY_ROI_TARGET,
    LEVERAGE,
    LIVE_TRADING,
    MARGIN_PCT,
    POLL_INTERVAL_SEC,
    STOP_LOSS_PCT,
    SYMBOL,
    TAKE_PROFIT_PCT,
    USE_TESTNET,
)
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
    log.info(f"SL={STOP_LOSS_PCT*100:.2f}%  TP={TAKE_PROFIT_PCT*100:.2f}%")
    log.info(f"Daily target={DAILY_ROI_TARGET*100:.0f}%  Daily loss cap={DAILY_LOSS_LIMIT*100:.0f}%")

    if not LIVE_TRADING:
        log.warning("DRY RUN MODE — no real orders will be placed. Set LIVE_TRADING=true in .env to enable.")

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
            if pos:
                amt = float(pos["positionAmt"])
                upnl = float(pos["unRealizedProfit"])
                log.info(
                    f"holding amt={amt}  uPnL={upnl:+.2f}  equity={equity:.2f}  dayROI={risk.roi(equity)*100:+.2f}%"
                )
                time.sleep(POLL_INTERVAL_SEC)
                continue

            df = api.klines(limit=100)
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

            if signal == "LONG":
                sl = price * (1 - STOP_LOSS_PCT)
                tp = price * (1 + TAKE_PROFIT_PCT)
            else:
                sl = price * (1 + STOP_LOSS_PCT)
                tp = price * (1 - TAKE_PROFIT_PCT)

            log.info(f"OPEN {signal}  qty={qty}  entry≈{price:.2f}  SL={sl:.2f}  TP={tp:.2f}")

            if LIVE_TRADING:
                api.cancel_open_orders()
                api.open_position(signal, qty, sl, tp)
            else:
                log.info("(dry run — order not sent)")

            time.sleep(POLL_INTERVAL_SEC)

        except KeyboardInterrupt:
            log.info("interrupted, exiting")
            sys.exit(0)
        except Exception as e:
            log.exception(f"loop error: {e}")
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
