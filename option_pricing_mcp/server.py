"""MCP server exposing the Option-Pricing-Library as tools.

All pricing / calibration logic comes from the original library by T1mR0m:
https://github.com/T1mR0m/Option-Pricing-Library
This module only adapts it to the Model Context Protocol.
"""

from __future__ import annotations

import contextlib
import functools
import math
import sys
from datetime import datetime
from typing import Any, Literal

import numpy as np
import yfinance as yf
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from core.mixins import FiniteDifferenceGreeksMixin

from market_data.data_loader import MarketDataLoader
from market_data.vol_estimators import VolatilityEstimator
from products.american import AmericanOption
from products.asian import AsianOption
from products.autocallable import Autocallable
from products.barrier import BarrierOption
from products.binary import BinaryOption
from products.european import EuropeanOption
from vol_calibration.implied_vol import ImpliedVolCalibrator
from vol_calibration.vol_surface import VolatilitySurface

mcp = MCPServer(
    "option-pricing",
    instructions=(
        "Price vanilla and exotic options (European, American, Asian, Barrier, "
        "Binary, Autocallable), compute Greeks, back out implied volatility and "
        "pull live market data from Yahoo Finance. Rates, yields and vols are "
        "decimals (0.05 = 5%), T is in years. Educational use only, not "
        "financial advice. Built on https://github.com/T1mR0m/Option-Pricing-Library"
    ),
)

Style = Literal["european", "american", "asian", "barrier", "binary", "autocallable"]
OptType = Literal["call", "put"]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _stdout_safe(fn):
    """The stdio transport owns stdout; route library print() calls to stderr.

    Also turns input/validation errors into ToolErrors so the client sees the message.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        with contextlib.redirect_stdout(sys.stderr):
            try:
                return fn(*args, **kwargs)
            except (ValueError, KeyError, ZeroDivisionError) as e:
                raise ToolError(f"{type(e).__name__}: {e}") from e

    return wrapper


class _SafeLoader(MarketDataLoader):
    """MarketDataLoader that never blocks on input() and tolerates missing dividends.

    The original falls back to interactive input() for the risk-free rate, which
    would read from the MCP protocol stream, so here it raises (or uses an override).
    """

    def __init__(self, ticker: str, r_override: float | None = None):
        super().__init__(ticker)
        self._r_override = r_override

    def get_risk_free_rate(self):
        if self._r_override is not None:
            return self._r_override
        df = yf.Ticker("^IRX").history(period="5d")
        if df.empty:
            raise ValueError(
                "Could not fetch the 13-week T-bill rate (^IRX) from Yahoo Finance; "
                "pass risk_free_rate explicitly."
            )
        return float(df["Close"].iloc[-1]) * 0.01

    def get_div_yield(self):
        try:
            return float(super().get_div_yield())
        except (TypeError, ZeroDivisionError):
            return 0.0  # no dividend info (e.g. non-dividend stock)


class _ExpiryLimitedTicker:
    """Proxy around a yfinance Ticker that exposes only the given expirations."""

    def __init__(self, ticker, expirations):
        self._ticker = ticker
        self.options = tuple(expirations)

    def __getattr__(self, name):
        return getattr(self._ticker, name)


def _clean(value: Any) -> Any:
    """Convert numpy / pandas scalars to JSON-friendly Python values."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _build_option(
    style: str,
    S: float, K: float, sigma: float, r: float, T: float, opt_type: str, q: float,
    barrier: float | None, barrier_type: str | None, continuous_monitoring: bool,
    average_type: str, payout: float | None,
    autocall_barrier: float | None, protection_barrier: float | None,
    coupon_rate: float | None, observation_steps: list[int] | None,
):
    common = dict(S=S, K=K, sigma=sigma, r=r, q=q, T=T, opt_type=opt_type)
    if style == "european":
        return EuropeanOption(**common)
    if style == "american":
        return AmericanOption(**common)
    if style == "asian":
        return AsianOption(**common, average_type=average_type)
    if style == "barrier":
        if barrier is None or barrier_type is None:
            raise ValueError("barrier options need `barrier` and `barrier_type`")
        return BarrierOption(**common, B=barrier, barrier_type=barrier_type,
                             continuous=continuous_monitoring)
    if style == "binary":
        return BinaryOption(**common, Q=payout if payout is not None else 1.0)
    if style == "autocallable":
        if None in (autocall_barrier, protection_barrier, coupon_rate):
            raise ValueError("autocallables need `autocall_barrier`, "
                             "`protection_barrier` and `coupon_rate`")
        return Autocallable(**common, autocallable_barrier=autocall_barrier,
                            protection_barrier=protection_barrier,
                            coupon_rate=coupon_rate,
                            obs_indices=observation_steps or [252, 504, 756])
    raise ValueError(f"unknown option style: {style}")


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #

@mcp.tool()
@_stdout_safe
def price_option(
    style: Style,
    spot: float,
    strike: float,
    volatility: float,
    risk_free_rate: float,
    time_to_expiry: float,
    option_type: OptType = "call",
    dividend_yield: float = 0.0,
    method: Literal["default", "monte_carlo"] = "default",
    include_greeks: bool = True,
    barrier: float | None = None,
    barrier_type: Literal["up-and-out", "up-and-in", "down-and-out", "down-and-in"] | None = None,
    continuous_monitoring: bool = False,
    average_type: Literal["arithmetic", "geometric"] = "arithmetic",
    payout: float | None = None,
    autocall_barrier: float | None = None,
    protection_barrier: float | None = None,
    coupon_rate: float | None = None,
    observation_steps: list[int] | None = None,
    n_sims: int = 100_000,
    n_steps: int | None = None,
    seed: int = 123,
    greeks_spot_bump: float = 0.01,
) -> dict:
    """Price an option and (optionally) compute its Greeks.

    Models per style:
      - european: Black-Scholes closed form (method="monte_carlo" for antithetic MC)
      - american: Cox-Ross-Rubinstein binomial tree (n_steps = tree steps, default 500)
      - asian: arithmetic/geometric average, antithetic Monte Carlo
      - barrier: Monte Carlo; needs `barrier` + `barrier_type`;
        continuous_monitoring applies the Broadie-Glasserman-Kou correction
      - binary: cash-or-nothing paying `payout` (default 1); closed form or MC
      - autocallable: Monte Carlo; needs autocall_barrier, protection_barrier,
        coupon_rate (annual); observation_steps are path-step indices
        (default [252, 504, 756] = yearly over 3 years with n_steps=756)

    Units: rates/yields/vols are decimals, time_to_expiry in years.
    Greeks: vega and rho per 1% move, theta per trading day (1/252).
    European Greeks are analytical; others use finite differences
    (bump & reprice; delta/gamma bump spot by `greeks_spot_bump` x spot).
    That is slow for Monte Carlo products, especially autocallables, so lower
    n_sims or set include_greeks=False there.
    """
    opt = _build_option(
        style, spot, strike, volatility, risk_free_rate, time_to_expiry,
        option_type, dividend_yield, barrier, barrier_type, continuous_monitoring,
        average_type, payout, autocall_barrier, protection_barrier, coupon_rate,
        observation_steps,
    )

    mc_kwargs: dict[str, Any] = {"n_sims": n_sims, "seed": seed}
    if n_steps is not None:
        mc_kwargs["n_steps"] = n_steps

    result: dict[str, Any] = {"style": style, "option_type": option_type}
    std_error = None

    if style == "american":
        tree = {"n_steps": n_steps} if n_steps is not None else {}
        opt.price = functools.partial(opt.price, **tree)  # greeks reuse this
        price = opt.price()
        result["model"] = "CRR binomial tree"
    elif style in ("european", "binary"):
        if method == "monte_carlo":
            price, std_error = opt.price_mc(**mc_kwargs, return_se=True)
            result["model"] = "Monte Carlo (antithetic)"
        else:
            price = opt.price()
            result["model"] = "Black-Scholes closed form"
    else:
        # Bind MC settings to the instance so finite-difference Greeks reuse them.
        opt.price = functools.partial(opt.price, **mc_kwargs)
        out = opt.price(return_se=True)
        price, std_error = out if isinstance(out, tuple) else (out, 0.0)
        result["model"] = "Monte Carlo (antithetic)"

    result["price"] = price
    if std_error is not None:
        result["std_error"] = std_error
    if include_greeks:
        if style == "european":
            result["greeks"] = opt.greeks()  # analytical
        else:
            # Products inherit (Option, FiniteDifferenceGreeksMixin), so their
            # super().greeks() resolves to the abstract Option.greeks; call the
            # mixin directly.
            # A relative spot bump (default 1%) keeps gamma stable for
            # tree / Monte Carlo prices, which are not smooth at tiny bumps.
            result["greeks"] = FiniteDifferenceGreeksMixin.greeks(
                opt, ds=spot * greeks_spot_bump
            )
    return _clean(result)


@mcp.tool()
@_stdout_safe
def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    risk_free_rate: float,
    time_to_expiry: float,
    option_type: OptType = "call",
    dividend_yield: float = 0.0,
    style: Literal["european", "american"] = "european",
    initial_vol: float = 0.2,
) -> dict:
    """Back out implied volatility from an observed option price (Newton-Raphson).

    European uses Black-Scholes; american uses the CRR tree with
    finite-difference vega (slower).
    """
    cls = EuropeanOption if style == "european" else AmericanOption
    opt = cls(S=spot, K=strike, sigma=initial_vol, r=risk_free_rate,
              q=dividend_yield, T=time_to_expiry, opt_type=option_type)
    iv = ImpliedVolCalibrator(opt, target_price=market_price).calc_iv_newton_raphson(
        initial_vol=initial_vol
    )
    return _clean({"implied_volatility": iv, "style": style})


@mcp.tool()
@_stdout_safe
def get_market_data(ticker: str, history_period: str = "1y", hv_window: int = 30) -> dict:
    """Fetch live inputs for a ticker from Yahoo Finance.

    Returns spot, dividend yield, risk-free rate (13-week T-bill ^IRX),
    historical volatility over `hv_window` days, a GARCH(1,1) next-day
    volatility forecast (both annualised) and available option expirations.
    """
    loader = _SafeLoader(ticker.upper())
    loader.fetch_historical_data(period=history_period)
    est = VolatilityEstimator(loader.get_log_returns())

    try:
        r = loader.get_risk_free_rate()
    except ValueError as e:
        r = None
        r_error = str(e)
    else:
        r_error = None

    data = {
        "ticker": ticker.upper(),
        "as_of": loader.get_latest_market_date(),
        "spot": loader.get_spot_price(),
        "dividend_yield": loader.get_div_yield(),
        "risk_free_rate": r,
        "historical_volatility": est.calc_historical_volatility(window=hv_window),
        "garch_volatility": est.calc_garch_volatility(),
        "option_expirations": list(loader.yfticker.options),
    }
    if r_error:
        data["risk_free_rate_error"] = r_error
    return _clean(data)


@mcp.tool()
@_stdout_safe
def analyze_listed_option(
    ticker: str,
    expiration_date: str,
    strike: float,
    option_type: OptType = "call",
    style: Literal["european", "american"] = "european",
    risk_free_rate: float | None = None,
) -> dict:
    """Compare a listed option's market price with the model (like the library's main.py).

    Picks the listed contract closest to `expiration_date` (YYYY-MM-DD) and
    `strike`, prices it with GARCH(1,1) volatility, and calibrates implied
    volatility from the bid/ask mid (or last price).
    """
    loader = _SafeLoader(ticker.upper(), r_override=risk_free_rate)
    spot = loader.get_spot_price()
    q = loader.get_div_yield()
    r = loader.get_risk_free_rate()
    garch_sigma = VolatilityEstimator(loader.get_log_returns()).calc_garch_volatility()

    row, target_date = loader.get_closest_option(expiration_date, option_type, strike)
    today = loader.get_latest_market_date()
    T = (datetime.strptime(target_date, "%Y-%m-%d").date() - today).days / 365.0
    if T <= 0:
        raise ValueError(f"expiration {target_date} is not after market date {today}")

    bid, ask = float(row["bid"]), float(row["ask"])
    market_price = (bid + ask) / 2 if bid > 0 and ask > 0 else float(row["lastPrice"])

    cls = EuropeanOption if style == "european" else AmericanOption
    opt = cls(S=spot, K=float(row["strike"]), sigma=garch_sigma, r=r, q=q,
              T=T, opt_type=option_type)
    model_price = opt.price()

    try:
        iv = ImpliedVolCalibrator(opt, target_price=market_price).calc_iv_newton_raphson(
            initial_vol=garch_sigma
        )
        iv_error = None
    except ValueError as e:
        iv, iv_error = None, str(e)

    result = {
        "ticker": ticker.upper(),
        "contract": row.get("contractSymbol"),
        "expiration": target_date,
        "strike": row["strike"],
        "time_to_expiry": T,
        "spot": spot,
        "dividend_yield": q,
        "risk_free_rate": r,
        "bid": bid,
        "ask": ask,
        "last_price": row["lastPrice"],
        "last_trade_date": row["lastTradeDate"],
        "market_price": market_price,
        "yahoo_quoted_iv": row["impliedVolatility"],
        "garch_volatility": garch_sigma,
        "model_price_garch": model_price,
        "calibrated_iv": iv,
    }
    if iv_error:
        result["calibrated_iv_error"] = iv_error
    return _clean(result)


@mcp.tool()
@_stdout_safe
def build_volatility_surface(
    ticker: str,
    moneyness_min: float = 0.8,
    moneyness_max: float = 1.2,
    min_volume: int = 1,
    min_maturity_days: float = 7,
    max_expirations: int = 6,
    risk_free_rate: float | None = None,
) -> dict:
    """Calibrate an implied-volatility surface from the live option chain.

    Uses OTM calls and puts within the moneyness band, filters illiquid quotes,
    and solves Black-Scholes IV per strike with Newton-Raphson. Only the first
    `max_expirations` expirations at least `min_maturity_days` out are scanned
    (each is a network call).
    Returns one point per (strike, expiry): strike, moneyness, log moneyness,
    expiration, time to maturity, option type, market price, calibrated IV.
    """
    loader = _SafeLoader(ticker.upper(), r_override=risk_free_rate)
    today = loader.get_latest_market_date()
    eligible = [
        d for d in loader.yfticker.options
        if (datetime.strptime(d, "%Y-%m-%d").date() - today).days >= min_maturity_days
    ]
    loader.yfticker = _ExpiryLimitedTicker(loader.yfticker, eligible[:max_expirations])

    df = VolatilitySurface(
        data_loader=loader,
        option_class=EuropeanOption,
        moneyness_range=(moneyness_min, moneyness_max),
        min_volume=min_volume,
        min_maturity=min_maturity_days / 365,
    ).build_surface()

    points = [] if df.empty else df.dropna(subset=["Calibrated IV"]).to_dict("records")
    return _clean({
        "ticker": ticker.upper(),
        "spot": loader.get_spot_price(),
        "expirations_scanned": list(loader.yfticker.options),
        "n_points": len(points),
        "points": points,
    })


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
