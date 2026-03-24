# 🧬 Aether AI — Intelligent Portfolio Management Platform

AI-driven portfolio management with regime-switching, multi-agent analysis, and MPT optimization.

## 📊 What It Does

- **Multi-Agent AI Analysis**: 5 specialized AI agents (Macro, Micro, Sentiment, Technical, Supervisor) analyze 19 assets in real-time
- **Regime-Switching Portfolios**: Automatically detects market regimes (Risk On/Off/Neutral) and recommends one of 4 risk profiles
- **MPT Optimization**: Markowitz Mean-Variance optimization for each risk profile
- **Self-Learning Feedback Loop**: AI evaluates its own historical regime switches, identifies mistakes, and adjusts parameters (with overfitting safeguards)
- **Signal-Weight Optimization**: Ridge regression identifies which technical signals actually predict returns (ROC 10d = 97.9% weight, RSI = irrelevant)
- **Momentum-Based Sector Rotation**: 3-month risk-adjusted momentum ranking for sector/region ETFs

## 🏗️ Architecture

```
Frontend (React + TypeScript + Vite)
├── Dashboard — Market overview, AI insights, regime indicator
├── Portfolio — 4 risk profiles with MPT allocations
├── Sectors — Sector ETF analysis with AI scoring
├── Regions — Regional ETF momentum ranking
├── Backtest — Historical regime-switching backtest
├── AI Prestanda — Model performance tracking
└── Nyheter — Real-time news with sentiment analysis

Backend (Python + FastAPI)
├── main.py — API endpoints, regime detection, scoring pipeline
├── ai_engine.py — Multi-agent orchestration
├── portfolio_optimizer.py — MPT optimization (19 assets, 4 profiles)
├── composite_backtest.py — Regime-switching backtest (T+1 delay, slippage)
├── signal_optimizer.py — Ridge regression signal weight training
├── agents/
│   ├── supervisor_agent.py — Weighted final scoring (learned signal weights)
│   ├── macro_agent.py — Macro/economic analysis
│   ├── micro_agent.py — Asset-specific fundamentals
│   ├── sentiment_agent.py — News sentiment (NLP)
│   └── technical_agent.py — Technical indicators
├── data_service.py — Market data fetching + caching
├── news_service.py — Real-time RSS + Marketaux news
└── feedback_loop.py — Self-evaluation + overfitting guard
```

## 📈 19 Assets Tracked

| Category | Assets |
|----------|--------|
| **Core Macro** | Bitcoin, Gold, Silver, Oil, S&P 500, ACWI, EUR/USD, US 10Y |
| **Sectors** | Finance (XLF), Energy (XLE), Tech (XLK), Health (XLV), Defense (ITA) |
| **Regions** | Emerging Markets (EEM), Europe (VGK), Japan (EWJ), India (INDA) |
| **Leveraged** | S&P 500 2x (SSO), Nasdaq 2x (QLD) |

## 🔥 4 Risk Profiles

| Profile | Strategy | Leverage |
|---------|----------|----------|
| 🛡️ Försiktig | Min variance, capital preservation | 0x |
| ⚖️ Balanserad | Max Sharpe (tangent portfolio) | 0x |
| 🚀 Aggressiv | Max return on efficient frontier | 0x |
| 🔥 Turbo | Aggressive + 20% leveraged ETFs | 2x (partial) |

## 🧠 Key ML/Quant Features

### Signal Weight Optimization
- Ridge regression (α=10) trained on 5000+ data points
- Discovered: ROC 10d is 250x more predictive than RSI
- Weights automatically applied to supervisor agent scoring

### Regime Detection
- Multi-factor: ROC 10d (70%) + Momentum 20d (15%) + Volatility (15%)
- Replaces SMA crossover (proven to have zero predictive power)

### Realistic Backtest
- **T+1 execution delay** — signal day N, trade day N+1
- **3-day confirmation** — regime must hold 3 days (anti-whipsaw)
- **0.10% slippage** per trade (bid/ask spread)
- Result: **+19.8% return, Sharpe 0.78, Alpha +5.7% vs S&P 500**

### Self-Learning Feedback Loop
- Evaluates every regime switch historically
- Identifies missed drawdowns
- Adjusts parameters with overfitting guards (min 3 data points, confidence thresholds)

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+
- Google Gemini API key (free tier works)

### Setup
```bash
# Frontend
npm install
npm run dev

# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python -m uvicorn main:app --reload --port 8000
```

### API Keys Required
| Key | Purpose | Required |
|-----|---------|----------|
| `GOOGLE_API_KEY` | Gemini AI agents | ✅ Yes |
| `MARKETAUX_API_KEY` | Real-time news | Optional |
| `ANTHROPIC_API_KEY` | Claude (premium) | Optional |

## 📁 Key Files

| File | Purpose |
|------|---------|
| `backend/main.py` | All API endpoints + scoring pipeline |
| `backend/portfolio_optimizer.py` | MPT optimization + 4 profiles |
| `backend/composite_backtest.py` | Regime-switching backtest |
| `backend/signal_optimizer.py` | Ridge regression + momentum ranking |
| `backend/feedback_loop.py` | Self-evaluation engine |
| `backend/agents/supervisor_agent.py` | Learned-weight agent scoring |
| `src/pages/MyPortfolioPage.tsx` | Portfolio UI with 4 tabs |

## 📊 Backtest Results (Realistic)

| Metric | AI Portfolio | S&P 500 |
|--------|-------------|---------|
| Return (1Y) | +19.8% | +14.1% |
| Alpha | +5.7% | — |
| Sharpe Ratio | 0.78 | — |
| Max Drawdown | -11.0% | -12.5% |
| Trades | 17 | — |
| Slippage Cost | $1.91 | — |

---

Built with ❤️ by Aether AI
