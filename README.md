# Option Pricing MCP

An [MCP](https://modelcontextprotocol.io) server that lets Claude (or any MCP client) price options, compute Greeks, back out implied volatility and build volatility surfaces from live Yahoo Finance data.

> **All the quant work here is by [T1mR0m](https://github.com/T1mR0m).** This repo is a fork of his
> **[Option-Pricing-Library](https://github.com/T1mR0m/Option-Pricing-Library)**. The pricing models,
> calibration and market-data code (`core/`, `products/`, `market_data/`, `vol_calibration/`) are his,
> unchanged. This fork only adds the MCP layer in [`option_pricing_mcp/`](option_pricing_mcp/server.py).
> The library's original README is kept in [`LIBRARY_README.md`](LIBRARY_README.md). If you like this, star the
> [original repo](https://github.com/T1mR0m/Option-Pricing-Library).

## Tools

| Tool | What it does |
|---|---|
| `price_option` | European (Black-Scholes / MC), American (CRR tree), Asian, Barrier, Binary, Autocallable. Price, MC standard error, Greeks |
| `implied_volatility` | Newton-Raphson IV from a market price |
| `get_market_data` | Spot, dividend yield, risk-free rate (^IRX), historical and GARCH(1,1) vol, option expirations |
| `analyze_listed_option` | Compare a listed contract's market price with the model and calibrate its IV |
| `build_volatility_surface` | IV surface from the live option chain (OTM, liquidity-filtered) |

## Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). Nothing else needs to be installed by hand.

**Claude Code**

```bash
claude mcp add option-pricing -- uvx --from git+https://github.com/thekogit/option-pricing-mcp option-pricing-mcp
```

**Claude Desktop / Cursor / other clients:** add this to the MCP config (`claude_desktop_config.json`, `.cursor/mcp.json`, …):

```json
{
  "mcpServers": {
    "option-pricing": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/thekogit/option-pricing-mcp", "option-pricing-mcp"]
    }
  }
}
```

**From a local clone**

```bash
git clone https://github.com/thekogit/option-pricing-mcp
cd option-pricing-mcp
uv run option-pricing-mcp   # or: pip install . && option-pricing-mcp
```

Then ask something like *"Price a 1-year down-and-out put on AAPL at the money with a 90% barrier using live market data."*

## Notes

- Units: rates, yields and vols are decimals (`0.05` = 5%); time is in years. Vega and rho are per 1%, theta per trading day.
- Market data comes from Yahoo Finance via `yfinance` (unofficial, may be delayed or rate-limited).
- **Educational use only. Not financial advice.** (Same disclaimer as the original library.)

## License

MIT. Original copyright © 2026 T1mR0m, see [LICENSE](LICENSE).
