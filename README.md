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

You only need [uv](https://docs.astral.sh/uv/getting-started/installation/). The server starts with this command, and `uvx` fetches the code and dependencies on first run:

```bash
uvx --from git+https://github.com/thekogit/option-pricing-mcp option-pricing-mcp
```

Pick your client below. If a GUI app says `uvx` is not found, replace `"uvx"` with its full path (`which uvx` / `where uvx`).

### Claude Code

```bash
claude mcp add option-pricing -- uvx --from git+https://github.com/thekogit/option-pricing-mcp option-pricing-mcp
```

Add `--scope user` to enable it in every project. Check with `/mcp`.

### Claude Desktop

Settings → Developer → Edit Config, or edit the file directly:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

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

Restart Claude Desktop.

### Cursor

Put the same `mcpServers` JSON as Claude Desktop in `~/.cursor/mcp.json` (global) or `.cursor/mcp.json` (one project). Restart Cursor, then toggle the server under **Customize** in the sidebar if needed.

### Antigravity (agy)

Same `mcpServers` JSON as above, in `~/.gemini/config/mcp_config.json` (global) or `<workspace>/.agents/mcp_config.json` (one workspace).
In the IDE: agent panel **…** → MCP Servers → Manage MCP Servers → View raw config. Save it, then refresh or reload from the `/mcp` manager.

### OpenCode

```bash
opencode mcp add option-pricing --global -- uvx --from git+https://github.com/thekogit/option-pricing-mcp option-pricing-mcp
```

Or edit `~/.config/opencode/opencode.json` (global) or `opencode.json` in the project. Note the OpenCode format: `command` is a single array, nested under `mcp.servers`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "option-pricing": {
        "type": "local",
        "command": ["uvx", "--from", "git+https://github.com/thekogit/option-pricing-mcp", "option-pricing-mcp"]
      }
    }
  }
}
```

Check it with `/mcps`. Older OpenCode 1.x puts servers directly under `"mcp"` (no `"servers"`) with `"enabled": true`.

### Pi

Pi 0.99+ has built-in MCP. Put the same `mcpServers` JSON as Claude Desktop in `~/.pi/agent/mcp.json` (global) or `.pi/mcp.json` (trusted project), then run `/reload` and check `/mcp`.
If you use the [`pi-mcp-adapter`](https://github.com/nicobailon/pi-mcp-adapter) extension instead (`pi install npm:pi-mcp-adapter`), the same JSON goes in `~/.config/mcp/mcp.json` or `.mcp.json`.

### Hermes Agent

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  option-pricing:
    command: "uvx"
    args: ["--from", "git+https://github.com/thekogit/option-pricing-mcp", "option-pricing-mcp"]
```

Then start a new session or run `/reload-mcp`.

### From a local clone (any client)

```bash
git clone https://github.com/thekogit/option-pricing-mcp
cd option-pricing-mcp
uv run option-pricing-mcp   # or: pip install . && option-pricing-mcp
```

To run the local copy from a client, use `"command": "uv", "args": ["run", "--directory", "/path/to/option-pricing-mcp", "option-pricing-mcp"]`.

### Try it

*"Price a 1-year down-and-out put on AAPL at the money with a 90% barrier using live market data."*

The first call takes 10–30 s while `uvx` installs numpy/scipy/pandas. Later starts are instant.

## Notes

- Units: rates, yields and vols are decimals (`0.05` = 5%); time is in years. Vega and rho are per 1%, theta per trading day.
- Market data comes from Yahoo Finance via `yfinance` (unofficial, may be delayed or rate-limited).
- **Educational use only. Not financial advice.** (Same disclaimer as the original library.)

## License

MIT. Original copyright © 2026 T1mR0m, see [LICENSE](LICENSE).
