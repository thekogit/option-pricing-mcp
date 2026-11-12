# Option-Pricing-Library

An object-oriented quantitative finance library for pricing vanilla and exotic options, complete with risk sensitivities (Greeks), numerical implied volatility calibration, and 3D volatility surface rendering via live market data integration.

This project implements standard industry pricing models and data pipelines from scratch to demonstrate the mathematical and computational mechanics of quantitative derivatives pricing, dependency injection, and microstructure noise filtering.

## Key Features

### 1. Volatility Surface Calibration
- **Newton-Raphson Root Finding:** Rapidly backs out Implied Volatility from live market option chains.
- **Microstructure Noise Filtering:** Cleans retail data feeds by dropping stale `lastPrice` quotes, filtering illiquid strikes, enforcing arbitrage bounds, and screening for maximum relative bid-ask spreads.
- **3D Interactive Visualization:** Utilizes `plotly` and `scipy.interpolate` (mesh-grid triangulation) to render rotatable, continuous implied volatility term structures and skews.

### 2. Supported Option Products
- **European:** Black-Scholes analytical & Monte Carlo.
- **American:** Cox-Ross-Rubinstein (CRR) Binomial Tree.
- **Barrier (Knock-in/out):** Monte Carlo with Broadie-Glasserman-Kou (BGK) continuity correction.
- **Asian (Arithmetic):** Path-dependent Monte Carlo.
- **Binary (Cash-or-nothing):** Analytical & Monte Carlo.
- **Autocallables:** Structured product pricing with coupon payouts and downside protection.

### 3. Quantitative Risk & Optimization
- Exact analytical Greeks for Black-Scholes.
- Finite Difference Methods (Forward and Central bump & reprice) for exotics and trees.
- Fully vectorized `numpy` Monte Carlo simulations with Antithetic Variates for variance reduction.

## 📂 Project Architecture

The library features a decoupled, enterprise-grade OOP hierarchy, separating data ingestion, product definition, and mathematical calibration.

```text
Option-Pricing-Library/
├── core/                   # Base classes and mixins (Option, PricingEngine)
├── market_data/            # Data ingestion (yfinance) and parameter calculation
├── products/               # Derivative payouts (European, Asian, Barrier, etc.)
├── vol_calibration/        # Newton-Raphson solvers and Surface DataFrame builders
├── notebooks/              # Jupyter dashboards for interactive 3D visualization
├── legacy/                 # Original cell-based research and mathematical documentation
└── main.py                 # Terminal execution hook
```

## Installation

1. Clone the repository:
   ```bash
   git clone [https://github.com/T1mR0m/Option-Pricing-Library.git](https://github.com/T1mR0m/Option-Pricing-Library.git)
   cd Option-Pricing-Library
   ```

2. Create and activate a new virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows use `.venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## 📊 Demo Usage

### 1. Building a 3D Implied Volatility Surface
Seamlessly ingest live market data, calibrate the IV for valid strikes across the term structure, and generate a continuous volatility surface DataFrame.

```python
from market_data.data_loader import MarketDataLoader
from products.european import EuropeanOption
from vol_calibration.vol_surface import VolatilitySurface

# 1. Ingest live market data
loader = MarketDataLoader("AAPL") 

# 2. Inject dependencies into the surface builder
surface_builder = VolatilitySurface(
    data_loader=loader, 
    option_class=EuropeanOption, 
    moneyness_range=(0.8, 1.2), 
    min_volume=1,
    min_maturity=7/365
)

# 3. Calibrate via Newton-Raphson and extract the DataFrame
surface_df = surface_builder.build_surface()
clean_surface_df = surface_df.dropna(subset=['Calibrated IV'])

print(clean_surface_df.head())
```
*(Note: For the full 3D interactive Plotly rendering, see `notebooks/iv_surface.ipynb`)*

### 2. Pricing an Exotic Option (Down-and-Out Put)
```python
from products.barrier import BarrierOption

barrier_put = BarrierOption(
    S=100.0, K=100.0, B=90.0, 
    sigma=0.20, r=0.05, q=0.0, T=1.0, 
    opt_type="put", barrier_type="down-and-out"
)
mc_price, mc_se = barrier_put.price()
print(f"MC Price: ${mc_price:.4f} (SE: {mc_se:.4f})")
```

## Historical Documentation
For a deep dive into the underlying stochastic calculus, discretization logic, and the evolution of this library from a functional script to a decoupled architecture, refer to `legacy/option_pricing.ipynb`.

##  Disclaimer
This library is for educational and academic research purposes only. Do not use this code to make actual financial, hedging, or trading decisions.