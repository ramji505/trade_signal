# 🇮🇳 TradeSignal India

> **Private Quantitative Intraday Trading Signal & Research System for NIFTY 50 Index & Options**

[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js%2015-000000.svg?style=flat&logo=next.js)](https://nextjs.org)
[![TypeScript](https://img.shields.io/badge/Language-TypeScript-3178C6.svg?style=flat&logo=typescript)](https://www.typescriptlang.org/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB.svg?style=flat&logo=python)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2016-336791.svg?style=flat&logo=postgresql)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Cache-Redis%207-DC382D.svg?style=flat&logo=redis)](https://redis.io/)
[![License](https://img.shields.io/badge/License-Proprietary%20%2F%20Research-blue.svg)](#disclaimer)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Hierarchical 12-Factor Scoring Engine](#hierarchical-12-factor-scoring-engine)
- [Indian F&O Statutory Charges Engine](#indian-fo-statutory-charges-engine)
- [Transparent Outcome Horizons Evaluation](#transparent-outcome-horizons-evaluation)
- [Project Directory Structure](#project-directory-structure)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Start with Docker](#quick-start-with-docker)
- [Manual Installation & Setup](#manual-installation--setup)
  - [1. Backend Setup](#1-backend-setup)
  - [2. Frontend Setup](#2-frontend-setup)
- [Configuration (.env)](#configuration-env)
- [API Reference](#api-reference)
- [Running Tests & Backtest Export](#running-tests--backtest-export)
- [Compliance & Risk Disclaimer](#compliance--risk-disclaimer)

---

## 🌟 Overview

**TradeSignal India** is a quantitative intraday research and decision-support platform engineered specifically for the Indian equity derivatives market (primarily **NIFTY 50**). 

The platform operates on a **Signal-Only Architecture** — it analyzes multi-timeframe price action, order flow volume, market regimes, option chain open interest (OI) dynamics, and statutory transaction costs to generate high-probability trade setups with rigorous risk parameters (Entry, Stop Loss, Target 1, Target 2).

---

## 🚀 Key Features

- 🎯 **Hierarchical 12-Factor Strategy Engine**: Evaluates market regime, multi-timeframe concordance (15m, 10m, 5m, 3m, 1m), VWAP, EMA alignment (9/21/50), volume expansion (RVOL > 1.25), RSI momentum zones, and candlestick patterns.
- ⚡ **Signal-Only Non-Custodial Architecture**: Eliminates execution risk and regulatory complexities by serving as an analytical research dashboard without automated broker order execution.
- 📊 **Indian Statutory Costs & Net P&L Engine**: Real-world post-trade cost accounting compliant with April 2026 NSE revisions (STT @ 0.15% on option sell turnover, NSE exchange turnover fees, SEBI turnover charges, Stamp Duty, GST @ 18%, and brokerages).
- ⏱️ **Transparent Multi-Horizon Outcome Evaluation**: Mathematically tracks trade signal performance across fixed forward horizons (+1m, +3m, +5m, +10m, +15m, +20m) with strict **"Stop-loss touched first = Loss"** classification to avoid survivorship bias.
- 📈 **TradingView Lightweight Charts**: Smooth 60 FPS candlestick charts with overlaid signals, multi-timeframe badges, and support/resistance markers.
- ⛓️ **Options & Greeks Analytics**: Computes Black-Scholes Greeks (Delta, Gamma, Theta, Vega), Strike Selection (ATM/ITM delta ~0.45-0.60), Put-Call Ratio (PCR), and Open Interest (OI) Walls / Max Pain levels.
- 🛡️ **Risk & Volatility Circuit Breakers**: Event-risk penalties (RBI MPC meetings, Union Budget, US FOMC) and India VIX volatility adjustments to avoid false breakouts.
- 🔄 **Real-Time WebSocket & Telegram Alerts**: Instant signal broadcasting to browser clients via WebSockets and private Telegram Bot channels.

---

## 🏛️ System Architecture

```mermaid
flowchart TD
    subgraph Data Layer
        A1[Live Market Feed / Mock Provider] --> A2[Multi-Timeframe Candle Builder\n1m, 3m, 5m, 10m, 15m]
        A1 --> A3[Option Chain Feed\nOI, PCR, Greeks]
    end

    subgraph Strategy & Quantitative Core
        A2 --> B1[Regime & Trend Filter]
        A2 --> B2[Technical & Volume Indicators\nEMA, VWAP, RVOL, RSI]
        A3 --> B3[Derivatives & OI Walls Analyzer]
        
        B1 & B2 & B3 --> C1[12-Factor Hierarchical Scoring Engine]
        C1 --> C2{Score >= 70 Threshold?}
        C2 -- Yes --> D1[Signal Generator\nEntry, SL, TP1, TP2, Strike]
        C2 -- No --> D2[WAIT / Quality: NO_TRADE]
    end

    subgraph Risk & Cost Engine
        D1 --> E1[Statutory Cost Calculator\nSTT, GST, SEBI, Stamp, Brokerage]
        D1 --> E2[Circuit Breakers & Event Risk Filter]
        E1 & E2 --> F1[Trade Evaluation Engine\n+1m, +3m, +5m, +10m, +15m, +20m]
    end

    subgraph Delivery & Presentation
        F1 --> G1[FastAPI REST & WebSocket Endpoints]
        F1 --> G2[Telegram Alert Dispatcher]
        G1 --> H1[Next.js 15 UI Dashboard\nTradingView Charts, Backtest Panel]
        F1 --> H2[Output Artifacts\nJSON / CSV Reports]
    end
```

---

## 🎯 Hierarchical 12-Factor Scoring Engine

The scoring engine evaluates market conditions across three tiers, yielding a composite quality score from `0` to `100`:

| Tier | Component | Max Weight | Criteria |
| :--- | :--- | :---: | :--- |
| **Tier 1: Core Structure** | **MTF Agreement** | `+20 pts` | 15m (Regime) + 10m (Trend) + 5m (Setup) + 3m/1m alignment |
| | **Price Structure** | `+15 pts` | Higher-High/Higher-Low (HH/HL) or Break of Structure (BOS) |
| | **VWAP Position** | `+10 pts` | Price trading favorably relative to intraday VWAP |
| **Tier 2: Confirmation** | **EMA Alignment** | `+10 pts` | EMA 9 > EMA 21 > EMA 50 (Bullish) or reverse (Bearish) |
| | **Volume & RVOL** | `+10 pts` | Relative Volume > 1.25x expanding on trigger candle |
| | **RSI Momentum** | `+10 pts` | Bullish: 55–72 \| Bearish: 28–45 (Not Overbought/Oversold) |
| | **Candle Pattern** | `+5 pts` | Hammer, Shooting Star, Bullish/Bearish Engulfing |
| **Tier 3: Risk Penalties** | **S/R Proximity** | `-20 pts` | Immediate resistance/support within 0.25% of entry |
| | **Extreme Volatility**| `-20 pts` | Unfavorable ATR spikes or abnormal spread widening |
| | **Event Risk** | `-25 pts` | High-impact scheduled announcements (RBI policy, etc.) |

### Quality Classifications:
- 🟢 **VERY_STRONG** (`85–100`): Maximum conviction, optimal risk-to-reward ratio.
- 🔵 **STRONG** (`75–84`): High conviction, full confirmation.
- 🟡 **MODERATE** (`65–74`): Standard setup, potential tight trailing stop.
- 🟠 **WEAK** (`50–64`): Sub-optimal alignment, setup ignored.
- 🔴 **NO_TRADE** (`< 50`): Regime conflict or severe risk penalty.

---

## 💰 Indian F&O Statutory Charges Engine

The system computes real-world net post-cost profitability using the official Indian F&O fee structure:

```
Net P&L = Gross P&L - (Brokerage + STT + Exchange Charges + SEBI Charges + Stamp Duty + GST)
```

- **Brokerage**: Flat ₹20 per executed order (₹40 round-trip).
- **STT (Securities Transaction Tax)**: 0.15% on Option SELL turnover (effective April 1, 2026 NSE/Union Budget rate).
- **Exchange Turnover Charge (NSE)**: 0.03503% (₹35.03 per crore) of total premium turnover.
- **SEBI Turnover Fee**: ₹10 per crore (0.0001% of turnover).
- **Stamp Duty**: 0.003% on BUY turnover.
- **GST**: 18% on (Brokerage + Exchange Charges + SEBI Fees).

---

## ⏱️ Transparent Outcome Horizons Evaluation

To guarantee quantitative authenticity and eliminate selection bias:
1. Every generated signal is logged with its timestamp and trigger price.
2. The trade path is evaluated at **+1, +3, +5, +10, +15, and +20 minute** windows.
3. If price touches the **Stop Loss (SL)** at any tick before reaching the **Target (TP)**, the signal is permanently logged as a **LOSS**, regardless of any subsequent recovery.

---

## 📁 Project Directory Structure

```
trade-signal-india/
├── .env.example                     # Environment variables template
├── docker-compose.yml               # Multi-container orchestration (FastAPI, Next.js, Postgres, Redis)
├── README.md                        # Project documentation
├── backend/
│   ├── Dockerfile                   # Python FastAPI container configuration
│   ├── requirements.txt             # Python dependencies
│   ├── run_export.py                # Standalone backtesting & reporting script
│   ├── app/
│   │   ├── main.py                  # FastAPI application entrypoint & WebSocket endpoint
│   │   ├── api/                     # REST API route handlers
│   │   │   ├── backtest.py          # Backtest endpoints
│   │   │   ├── health.py            # Health check & system status
│   │   │   ├── market.py            # Candle and market data endpoints
│   │   │   ├── performance.py       # Performance & audit metrics
│   │   │   └── signals.py           # Real-time and historical signal feeds
│   │   ├── backtest/
│   │   │   └── engine.py            # Historical backtest simulation engine
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic v2 application settings
│   │   │   └── logging.py           # Structured logging configuration
│   │   ├── costs/
│   │   │   └── statutory_charges.py # Indian tax & statutory cost calculator
│   │   ├── data/
│   │   │   ├── base.py              # Abstract data feed interface
│   │   │   ├── candle_builder.py    # Multi-timeframe resampling engine
│   │   │   ├── data_quality.py      # Data validation & bad tick filtering
│   │   │   └── mock_provider.py     # Realistic NIFTY 50 tick & candle generator
│   │   ├── database/
│   │   │   ├── models.py            # SQLAlchemy async database models
│   │   │   └── session.py           # Database connection & session factory
│   │   ├── evaluation/
│   │   │   └── signal_evaluator.py  # Multi-horizon outcome tracker
│   │   ├── indicators/
│   │   │   ├── technical.py         # EMA, RSI, ATR, VWAP calculations
│   │   │   └── volume_analysis.py   # RVOL & Volume profile analysis
│   │   ├── ml/
│   │   │   └── features.py          # Quantitative feature extraction pipeline
│   │   ├── options/
│   │   │   ├── greeks.py            # Black-Scholes Greeks engine
│   │   │   ├── oi_walls.py          # Open Interest wall & Max Pain detector
│   │   │   ├── option_chain.py      # Option chain parser & organizer
│   │   │   ├── pcr.py               # Put-Call Ratio analyzer
│   │   │   └── strike_selection.py  # Delta-optimized strike selector
│   │   ├── risk/
│   │   │   ├── circuit_breakers.py  # Volatility & daily loss circuit breakers
│   │   │   ├── event_filter.py      # Economic calendar event filter
│   │   │   ├── risk_engine.py       # Position sizing & risk-to-reward validator
│   │   │   └── volatility.py        # India VIX & ATR adaptive limits
│   │   ├── strategy/
│   │   │   ├── candlestick.py       # Japanese candlestick pattern recognition
│   │   │   ├── derivatives.py       # Future & option confluence signals
│   │   │   ├── key_levels.py        # Pivot points & support/resistance levels
│   │   │   ├── market_regime.py     # Trending vs. Ranging market detector
│   │   │   ├── market_structure.py  # Swing highs/lows & BOS detector
│   │   │   ├── price_action.py      # Price action setup validator
│   │   │   ├── scoring.py           # 12-factor hierarchical scoring implementation
│   │   │   └── signal_engine.py     # Master signal synthesis engine
│   │   ├── telegram/
│   │   │   └── bot.py               # Telegram bot alert dispatcher
│   │   └── websocket/
│   │       └── manager.py           # WebSocket client connection manager
│   └── tests/
│       ├── test_backtest.py         # Backtesting engine test suite
│       ├── test_circuit_breakers.py # Risk circuit breaker unit tests
│       ├── test_costs.py            # Statutory charges unit tests
│       ├── test_health.py           # Health check API tests
│       ├── test_options.py          # Options & Greeks tests
│       └── test_strategy_and_evaluation.py # Scoring & evaluation test suite
├── frontend/
│   ├── Dockerfile                   # Next.js frontend container configuration
│   ├── package.json                 # Node dependencies & scripts
│   ├── tailwind.config.ts           # Tailwind CSS theme configuration
│   ├── tsconfig.json                # TypeScript compiler configuration
│   └── src/
│       ├── app/
│       │   ├── layout.tsx           # Global Next.js layout
│       │   ├── page.tsx             # Interactive dashboard page
│       │   └── globals.css          # Tailwind CSS styles
│       ├── components/
│       │   ├── Header.tsx           # Navigation & market status banner
│       │   ├── StatusCard.tsx       # System health & regime status cards
│       │   ├── TradingChart.tsx     # TradingView Lightweight Charts candlestick component
│       │   └── BacktestPanel.tsx    # Interactive backtest execution panel
│       └── types/
│           └── index.ts             # TypeScript interfaces & types
└── outputs/
    ├── backtest_latest.json         # Latest backtest run results
    ├── evaluations.csv              # Signal outcome evaluations log
    ├── performance.json             # Aggregate system performance metrics
    ├── signals_history.csv          # Historic signal logs
    └── trades_history.csv           # Detailed trade execution logs
```

---

## 🛠️ Tech Stack

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11+) with Asyncio
- **Data & Math**: [Pandas](https://pandas.pydata.org/), [NumPy](https://numpy.org/)
- **ORM & Storage**: [SQLAlchemy 2.0 (Async)](https://www.sqlalchemy.org/), [AsyncPG](https://github.com/MagicStack/asyncpg), [PostgreSQL 16](https://www.postgresql.org/)
- **Caching & Messaging**: [Redis 7](https://redis.io/)
- **Validation**: [Pydantic v2](https://docs.pydantic.dev/) & Pydantic-Settings
- **Testing**: [Pytest](https://pytest.org/) & Pytest-Asyncio

### Frontend
- **Framework**: [Next.js 15 (App Router)](https://nextjs.org/) + [React 19](https://react.dev/)
- **Language**: [TypeScript](https://www.typescriptlang.org/)
- **Styling**: [Tailwind CSS](https://tailwindcss.com/)
- **Charts**: [TradingView Lightweight Charts 5.x](https://tradingview.github.io/lightweight-charts/)
- **Icons**: [Lucide React](https://lucide.dev/)

---

## ⚡ Prerequisites

- **Python**: `3.11` or higher
- **Node.js**: `18.x` or higher (with `npm` or `pnpm`)
- **Docker & Docker Compose** (Optional, for containerized run)
- **PostgreSQL 16** & **Redis 7** (Optional for local mock mode, required for full live database persistence)

---

## 🐳 Quick Start with Docker

The easiest way to launch the entire stack (FastAPI Backend, Next.js Frontend, PostgreSQL, and Redis) is using Docker Compose:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/trade-signal-india.git
   cd trade-signal-india
   ```

2. **Create environment file**:
   ```bash
   cp .env.example .env
   ```

3. **Start all services**:
   ```bash
   docker-compose up --build
   ```

4. **Access the application**:
   - **Frontend UI**: [http://localhost:3000](http://localhost:3000)
   - **FastAPI Backend API**: [http://localhost:8000](http://localhost:8000)
   - **Interactive API Docs (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **ReDoc API Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 💻 Manual Installation & Setup

### 1. Backend Setup

```bash
cd backend

# 1. Create a virtual environment
python -m venv venv

# 2. Activate virtual environment
# On Linux/macOS:
source venv/bin/activate
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will start at `http://localhost:8000`.

### 2. Frontend Setup

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Run the Next.js development server
npm run dev
```

The frontend dashboard will be live at `http://localhost:3000`.

---

## ⚙️ Configuration (.env)

Configure your `.env` file based on `.env.example`:

```env
# Application Settings
APP_NAME="TradeSignal India"
APP_VERSION="0.1.0"
ENVIRONMENT="DEVELOPMENT"     # Options: DEVELOPMENT, MOCK, PAPER, LIVE_DATA
DEBUG=True

# Server
HOST="0.0.0.0"
PORT=8000

# Database & Cache
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=tradesignal_db
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tradesignal_db
REDIS_URL=redis://localhost:6379/0

# Telegram Bot (Optional for Live Alerts)
TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
TELEGRAM_CHAT_ID="your_telegram_chat_id"

# Broker API Integration (Optional)
BROKER_API_KEY=""
BROKER_API_SECRET=""
```

---

## 🔌 API Reference

### Health & Status
- `GET /health`: Comprehensive service health check, database status, and mode verification.
- `GET /`: Root application metadata.

### Market Data
- `GET /market/candles?symbol=NIFTY&timeframe=5m&count=100`: Retrieves historical OHLCV candles.
- `GET /market/option-chain?symbol=NIFTY`: Retrieves live/mock option chain with strike Greeks and PCR.

### Signals & Strategy
- `GET /signals/current`: Returns the latest 12-factor strategy decision, multi-timeframe state, score breakdown, and quality tier.
- `GET /signals/history`: Retrieves historical signals with trigger parameters and timestamps.

### Performance & Backtesting
- `GET /performance/summary`: Returns win rate, profit factor, net points, and statutory fee totals.
- `POST /backtest/run`: Executes backtest simulation over specified historical candle sets.

### Real-Time WebSocket
- `WS /ws`: Bi-directional WebSocket endpoint for live tick feeds, regime shifts, and instantaneous trade signal alerts.

---

## 🧪 Running Tests & Backtest Export

### Run Pytest Suite:
```bash
cd backend
pytest -v
```

### Run Standalone Backtest & Export Reports:
```bash
cd backend
python run_export.py
```
This generates:
- `outputs/backtest_latest.json`
- `outputs/performance.json`
- `outputs/trades_history.csv`

---

## ⚠️ Compliance & Risk Disclaimer

> **IMPORTANT NOTICE**:
> 
> 1. **Research & Educational Tool**: TradeSignal India is a private quantitative research platform and decision-support tool. It is **not** an automated trading bot, portfolio management service, or registered investment advisory service.
> 2. **No Guaranteed Returns**: Intraday trading in derivatives (Futures & Options) involves substantial financial risk. Past backtested performance is mathematical and does not guarantee future results.
> 3. **Regulatory Adherence**: This software does not execute live orders on user accounts. Users are exclusively responsible for their own trading decisions, order executions, and risk management.
> 4. **SEBI Disclosure**: Derivatives trading involves high risk. According to SEBI studies, 9 out of 10 individual traders in the equity F&O segment incur net losses.

---

<div align="center">
  <sub>Built with precision for Indian Quantitative & Derivatives Traders 🇮🇳</sub>
</div>

> Upgrade V2: strict live-data/authentication controls, options-aware scoring, current cost parameters, event-risk vetoes, and statistically honest backtest reporting.
