# ============================================================
# FIL: backend/data_enrichment.py (NY FIL — Fas 7 DEL A)
# Hämtar ALLA nya datakällor: makro, COT, bredd, options
# Utvidgar regime classifier med 16 nya features
# Total ny kostnad: 0 kr — all data via yfinance (gratis)
# ============================================================

import yfinance as yf
import pandas as pd
import numpy as np
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger("aether.data_enrichment")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "enrichment")
os.makedirs(DATA_DIR, exist_ok=True)


class DataEnrichmentLoader:
    """
    Hämtar alla nya datakällor för att utvidga regimklassificeraren
    från 15 till 31+ features. Inga nya agenter — bara bättre data.
    """

    def __init__(self):
        self.cache = {}

    # ================================================================
    # DEL A: MAKRO-FEATURES (6-8 nya)
    # ================================================================

    def fetch_macro_features(self) -> Dict[str, float]:
        """
        Hämtar makro-data via yfinance-proxies.
        Koppar ~ PMI (korrelation ~0.7), TLT ~ likviditet,
        IEF/TIP ratio ~ breakeven inflation, HYG/LQD ~ kreditspread.
        """
        features = {}

        # 1. Koppar som PMI-proxy (korrelerar ~0.7 med PMI)
        try:
            copper = yf.download("HG=F", period="3mo", interval="1d", progress=False)
            if isinstance(copper.columns, pd.MultiIndex):
                copper.columns = copper.columns.get_level_values(0)
            if len(copper) > 20:
                features["copper_roc_20d"] = float(
                    (copper["Close"].iloc[-1] / copper["Close"].iloc[-21] - 1) * 100
                )
                mean_252 = copper["Close"].rolling(252).mean()
                std_252 = copper["Close"].rolling(252).std()
                if len(mean_252.dropna()) > 0:
                    features["copper_level_zscore"] = float(
                        (copper["Close"].iloc[-1] - mean_252.iloc[-1])
                        / (std_252.iloc[-1] + 1e-8)
                    )
        except Exception as e:
            logger.warning(f"Copper fetch failed: {e}")

        # 2. TIPS breakeven inflation (daglig proxy)
        try:
            tip5 = yf.download("TIP", period="3mo", interval="1d", progress=False)
            ief = yf.download("IEF", period="3mo", interval="1d", progress=False)
            if isinstance(tip5.columns, pd.MultiIndex):
                tip5.columns = tip5.columns.get_level_values(0)
            if isinstance(ief.columns, pd.MultiIndex):
                ief.columns = ief.columns.get_level_values(0)
            if len(tip5) > 20 and len(ief) > 20:
                ratio = ief["Close"] / tip5["Close"]
                features["breakeven_inflation_proxy"] = float(
                    (ratio.iloc[-1] / ratio.iloc[-21] - 1) * 100
                )
        except Exception as e:
            logger.warning(f"TIPS breakeven failed: {e}")

        # 3. CRB Commodity Index proxy (DJP)
        try:
            crb = yf.download("DJP", period="3mo", interval="1d", progress=False)
            if isinstance(crb.columns, pd.MultiIndex):
                crb.columns = crb.columns.get_level_values(0)
            if len(crb) > 20:
                features["commodity_index_roc_20d"] = float(
                    (crb["Close"].iloc[-1] / crb["Close"].iloc[-21] - 1) * 100
                )
        except Exception as e:
            logger.warning(f"CRB proxy failed: {e}")

        # 4. HYG-LQD spread (kreditstress)
        try:
            hyg = yf.download("HYG", period="3mo", interval="1d", progress=False)
            lqd = yf.download("LQD", period="3mo", interval="1d", progress=False)
            if isinstance(hyg.columns, pd.MultiIndex):
                hyg.columns = hyg.columns.get_level_values(0)
            if isinstance(lqd.columns, pd.MultiIndex):
                lqd.columns = lqd.columns.get_level_values(0)
            if len(hyg) > 20 and len(lqd) > 20:
                spread = hyg["Close"] / lqd["Close"]
                features["credit_spread_level"] = float(spread.iloc[-1])
                features["credit_spread_change_10d"] = float(
                    (spread.iloc[-1] / spread.iloc[-11] - 1) * 100
                )
        except Exception as e:
            logger.warning(f"Credit spread failed: {e}")

        # 5. Likviditets-proxy via TLT (korrelerar med Fed-balansräkning)
        try:
            tlt = yf.download("TLT", period="3mo", interval="1d", progress=False)
            if isinstance(tlt.columns, pd.MultiIndex):
                tlt.columns = tlt.columns.get_level_values(0)
            if len(tlt) > 20:
                features["liquidity_proxy_roc_20d"] = float(
                    (tlt["Close"].iloc[-1] / tlt["Close"].iloc[-21] - 1) * 100
                )
        except Exception as e:
            logger.warning(f"Liquidity proxy failed: {e}")

        logger.info(f"Macro features: {len(features)} fetched")
        return features

    # ================================================================
    # DEL B: COT POSITIONERINGSDATA (2-3 nya features)
    # ================================================================

    def fetch_cot_data(self) -> Dict[str, float]:
        """
        CFTC Commitment of Traders — proxy via ETF-flöden.
        ETF-inflöden korrelerar ~0.6 med COT net positioning.
        Extremvärden = kontrarian-signal.
        """
        features = {}

        # GLD flows proxy: volym * prisförändring
        try:
            gld = yf.download("GLD", period="6mo", interval="1d", progress=False)
            if isinstance(gld.columns, pd.MultiIndex):
                gld.columns = gld.columns.get_level_values(0)
            if len(gld) > 60:
                vol_norm = gld["Volume"] / gld["Volume"].rolling(60).mean()
                price_chg = gld["Close"].pct_change()
                flow_proxy = vol_norm * price_chg
                flow_proxy = flow_proxy.dropna()

                if len(flow_proxy) >= 60:
                    current_val = float(flow_proxy.iloc[-1])
                    hist_vals = flow_proxy.iloc[-60:].values
                    percentile = float((current_val > hist_vals).mean() * 100)
                    features["gold_positioning_percentile"] = round(percentile, 1)

                    # Extremsignal: >90 = overcrowded long, <10 = overcrowded short
                    if percentile > 90:
                        features["gold_positioning_signal"] = -1  # Kontrarian: sälj
                    elif percentile < 10:
                        features["gold_positioning_signal"] = 1  # Kontrarian: köp
                    else:
                        features["gold_positioning_signal"] = 0
        except Exception as e:
            logger.warning(f"COT GLD proxy failed: {e}")

        # SPY flows proxy
        try:
            spy = yf.download("SPY", period="6mo", interval="1d", progress=False)
            if isinstance(spy.columns, pd.MultiIndex):
                spy.columns = spy.columns.get_level_values(0)
            if len(spy) > 60:
                vol_norm = spy["Volume"] / spy["Volume"].rolling(60).mean()
                price_chg = spy["Close"].pct_change()
                flow_proxy = vol_norm * price_chg
                flow_proxy = flow_proxy.dropna()

                if len(flow_proxy) >= 60:
                    current_val = float(flow_proxy.iloc[-1])
                    hist_vals = flow_proxy.iloc[-60:].values
                    percentile = float((current_val > hist_vals).mean() * 100)
                    features["equity_positioning_percentile"] = round(percentile, 1)
        except Exception as e:
            logger.warning(f"SPY COT proxy failed: {e}")

        logger.info(f"COT features: {len(features)} fetched")
        return features

    # ================================================================
    # DEL C: MARKNADSBREDD (3-4 nya features)
    # ================================================================

    def fetch_breadth_data(self) -> Dict[str, float]:
        """
        Marknadsbredd — marknadens interna hälsa.
        RSP/SPY ratio: sjunkande = smal marknad (farligt).
        Divergens: SPY stiger men RSP/SPY faller = bearish.
        """
        features = {}

        try:
            rsp = yf.download("RSP", period="6mo", interval="1d", progress=False)
            spy = yf.download("SPY", period="6mo", interval="1d", progress=False)
            if isinstance(rsp.columns, pd.MultiIndex):
                rsp.columns = rsp.columns.get_level_values(0)
            if isinstance(spy.columns, pd.MultiIndex):
                spy.columns = spy.columns.get_level_values(0)

            if len(rsp) > 50 and len(spy) > 50:
                # Align indexes
                common_idx = rsp.index.intersection(spy.index)
                rsp_aligned = rsp.loc[common_idx]
                spy_aligned = spy.loc[common_idx]

                ratio = rsp_aligned["Close"] / spy_aligned["Close"]
                features["breadth_ratio_current"] = float(ratio.iloc[-1])
                features["breadth_ratio_change_20d"] = float(
                    (ratio.iloc[-1] / ratio.iloc[-21] - 1) * 100
                )

                # Divergens: SPY stiger men RSP/SPY faller = bearish divergens
                spy_up_20d = bool(spy_aligned["Close"].iloc[-1] > spy_aligned["Close"].iloc[-21])
                ratio_down_20d = bool(ratio.iloc[-1] < ratio.iloc[-21])
                features["breadth_divergence"] = 1 if (spy_up_20d and ratio_down_20d) else 0

                # 50d breadth trend
                if len(ratio) > 50:
                    features["breadth_ratio_change_50d"] = float(
                        (ratio.iloc[-1] / ratio.iloc[-51] - 1) * 100
                    )

        except Exception as e:
            logger.warning(f"Breadth data failed: {e}")

        logger.info(f"Breadth features: {len(features)} fetched")
        return features

    # ================================================================
    # DEL D: OPTIONS-SIGNALER (3-5 nya features)
    # ================================================================

    def fetch_options_signals(self) -> Dict[str, float]:
        """
        Optionsmarknadens framåtblickande signaler.
        VIX terminsstruktur, fear ratio, kontrarian-signaler.
        """
        features = {}
        vix = None

        try:
            vix = yf.download("^VIX", period="3mo", interval="1d", progress=False)
            vix3m = yf.download("^VIX3M", period="3mo", interval="1d", progress=False)
            if isinstance(vix.columns, pd.MultiIndex):
                vix.columns = vix.columns.get_level_values(0)
            if isinstance(vix3m.columns, pd.MultiIndex):
                vix3m.columns = vix3m.columns.get_level_values(0)

            if len(vix) > 5 and len(vix3m) > 5:
                spot = float(vix["Close"].iloc[-1])
                term = float(vix3m["Close"].iloc[-1])

                # Contango (normalt): spot < futures
                # Backwardation (kris): spot > futures
                features["vix_term_structure"] = round(term - spot, 2)
                features["vix_in_backwardation"] = 1 if spot > term else 0
                features["vix_level"] = round(spot, 1)
        except Exception as e:
            logger.warning(f"VIX term structure failed: {e}")

        try:
            if vix is not None and len(vix) > 20:
                vix_sma20 = vix["Close"].rolling(20).mean()
                vix_ratio = float(vix["Close"].iloc[-1] / vix_sma20.iloc[-1])
                features["vix_fear_ratio"] = round(vix_ratio, 3)

                # Extremsignaler
                if vix_ratio > 1.3:
                    features["options_contrarian_signal"] = 1  # Extrem rädsla = köp
                elif vix_ratio < 0.75:
                    features["options_contrarian_signal"] = -1  # Extrem självgodhet = sälj
                else:
                    features["options_contrarian_signal"] = 0
        except Exception as e:
            logger.warning(f"Options signals failed: {e}")

        logger.info(f"Options features: {len(features)} fetched")
        return features

    # ================================================================
    # DEL E: MOMENTUM 12-MINUS-1 (per tillgång)
    # ================================================================

    def compute_12m1m_momentum(self, tickers: list = None) -> Dict[str, float]:
        """
        12-minus-1-month momentum: mest bevisade momentum-strategin.
        Avkastning senaste 12 månader exkl senaste månaden.
        """
        if tickers is None:
            tickers = ["SPY", "GLD", "TLT", "EEM", "XLE", "XLK", "XLF", "EWJ", "VGK"]

        features = {}

        for ticker in tickers:
            try:
                data = yf.download(ticker, period="14mo", interval="1d", progress=False)
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)
                if len(data) > 250:
                    price_12m_ago = float(data["Close"].iloc[-252]) if len(data) >= 252 else float(data["Close"].iloc[0])
                    price_1m_ago = float(data["Close"].iloc[-21])

                    # 12-minus-1: avkastning 12m exkl senaste månaden
                    mom_12m1m = (price_1m_ago / price_12m_ago - 1) * 100

                    ticker_key = ticker.lower().replace("=f", "").replace("^", "")
                    features[f"mom_12m1m_{ticker_key}"] = round(mom_12m1m, 2)
                    features[f"mom_signal_{ticker_key}"] = 1 if mom_12m1m > 0 else -1

            except Exception as e:
                logger.warning(f"Momentum {ticker} failed: {e}")

        logger.info(f"Momentum features: {len(features)} computed")
        return features

    # ================================================================
    # DEL F: KORRELATIONSREGIM (2-3 nya features)
    # ================================================================

    def compute_correlation_regime(self) -> Dict[str, float]:
        """
        När alla tillgångar rör sig åt samma håll = diversifiering dör.
        Stigande korrelation = tidig varningssignal (före VIX).
        """
        features = {}
        tickers = ["SPY", "GLD", "TLT", "EEM", "XLE", "VGK", "HYG"]

        try:
            data = yf.download(tickers, period="3mo", interval="1d", progress=False)

            # Handle MultiIndex columns from multi-ticker download
            if isinstance(data.columns, pd.MultiIndex):
                close_data = data["Close"]
            else:
                close_data = data

            returns = close_data.pct_change().dropna()

            if len(returns) > 20:
                # 20-dagars rullande korrelationsmatris
                recent_corr = returns.iloc[-20:].corr()

                # Genomsnittlig parvis korrelation (exkl diagonal)
                n = len(recent_corr.columns)
                corr_values = []
                for i in range(n):
                    for j in range(i + 1, n):
                        val = recent_corr.iloc[i, j]
                        if not np.isnan(val):
                            corr_values.append(abs(val))

                if corr_values:
                    avg_corr = float(np.mean(corr_values))
                    features["avg_cross_correlation_20d"] = round(avg_corr, 3)

                    # Jämför med 60-dagars korrelation
                    if len(returns) > 60:
                        older_corr = returns.iloc[-60:-20].corr()
                        older_values = []
                        for i in range(n):
                            for j in range(i + 1, n):
                                val = older_corr.iloc[i, j]
                                if not np.isnan(val):
                                    older_values.append(abs(val))

                        if older_values:
                            avg_older = float(np.mean(older_values))
                            features["correlation_regime_change"] = round(avg_corr - avg_older, 3)

                            # Varningssignal: korrelation stiger snabbt
                            if avg_corr > 0.50 and avg_corr > avg_older + 0.10:
                                features["correlation_regime_break"] = 1
                            else:
                                features["correlation_regime_break"] = 0
                        else:
                            features["correlation_regime_break"] = 0
                    else:
                        features["correlation_regime_break"] = 0

        except Exception as e:
            logger.warning(f"Correlation regime failed: {e}")

        logger.info(f"Correlation regime features: {len(features)} computed")
        return features

    # ================================================================
    # HUVUDMETOD: Hämta ALLA enrichment-features
    # ================================================================

    def fetch_all(self) -> Dict[str, float]:
        """
        Hämtar alla nya features i en enda metod.
        Returnerar flat dict med alla features.
        """
        all_features = {}

        logger.info("🔬 Starting data enrichment fetch...")

        # A: Makro (kreditspread, likviditet, breakeven, commodities)
        try:
            all_features.update(self.fetch_macro_features())
        except Exception as e:
            logger.error(f"Macro fetch failed entirely: {e}")

        # B: COT positionering (guld, aktier)
        try:
            all_features.update(self.fetch_cot_data())
        except Exception as e:
            logger.error(f"COT fetch failed entirely: {e}")

        # C: Marknadsbredd (equal-weight vs cap-weight)
        try:
            all_features.update(self.fetch_breadth_data())
        except Exception as e:
            logger.error(f"Breadth fetch failed entirely: {e}")

        # D: Options-signaler (VIX term, fear ratio)
        try:
            all_features.update(self.fetch_options_signals())
        except Exception as e:
            logger.error(f"Options fetch failed entirely: {e}")

        # E: 12-month momentum
        try:
            all_features.update(self.compute_12m1m_momentum())
        except Exception as e:
            logger.error(f"Momentum compute failed entirely: {e}")

        # F: Korrelationsregim
        try:
            all_features.update(self.compute_correlation_regime())
        except Exception as e:
            logger.error(f"Correlation regime failed entirely: {e}")

        logger.info(f"🔬 Data enrichment complete: {len(all_features)} total features")

        # Cacha
        self.cache = all_features
        self._save_cache(all_features)

        return all_features

    def _save_cache(self, features: Dict):
        """Spara features till disk-cache."""
        path = os.path.join(DATA_DIR, "latest_enrichment.json")
        try:
            with open(path, "w") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "features": features,
                    "n_features": len(features),
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")

    def load_cached(self) -> Optional[Dict]:
        """Ladda cachade features om de är färska (<12h)."""
        path = os.path.join(DATA_DIR, "latest_enrichment.json")
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                    age_hours = (
                        datetime.now() - datetime.fromisoformat(data["timestamp"])
                    ).total_seconds() / 3600
                    if age_hours < 12:  # Cache giltig i 12 timmar
                        logger.info(f"📦 Using cached enrichment ({age_hours:.1f}h old, {data.get('n_features', '?')} features)")
                        return data["features"]
                    else:
                        logger.info(f"📦 Cache expired ({age_hours:.1f}h old)")
            except Exception as e:
                logger.warning(f"Cache load failed: {e}")
        return None

    def get_features(self) -> Dict[str, float]:
        """Hämta features — från cache om färskt, annars ny fetch."""
        cached = self.load_cached()
        if cached:
            self.cache = cached
            return cached
        return self.fetch_all()

    # ================================================================
    # DIREKTSIGNALER (skickas till Supervisor, ej till klassificeraren)
    # ================================================================

    def get_direct_signals(self) -> List[Dict]:
        """
        Signaler som är så starka att de ska påverka Supervisor
        DIREKT, utöver regimklassificering.

        5 signaler:
        1. Breadth divergens (HIGH)
        2. VIX backwardation (CRITICAL)
        3. COT extremer (MEDIUM)
        4. Korrelations-spike (HIGH)
        5. Options kontrarian (MEDIUM)
        """
        features = self.cache or self.get_features()
        signals = []

        # 1. Breadth divergens
        if features.get("breadth_divergence") == 1:
            signals.append({
                "source": "market_breadth",
                "signal": "BEARISH_DIVERGENCE",
                "strength": "HIGH",
                "message": "S&P 500 stiger men marknadsbredden försämras. Historiskt föregår detta korrigering med 2-8 veckor.",
                "action": "OKA_KASSA_5PCT",
                "cash_impact_pct": 5,
                "affected_assets": ["sp500", "xlk", "xlf"],
            })

        # 2. VIX backwardation — KRITISK
        if features.get("vix_in_backwardation") == 1:
            signals.append({
                "source": "options_market",
                "signal": "VIX_BACKWARDATION",
                "strength": "CRITICAL",
                "message": "VIX i backwardation — marknaden prisar in kris som ÄNNU INTE synts i aktiepriser. Historiskt: 3-7 dagars förvarning.",
                "action": "OKA_KASSA_15PCT_OMEDELBART",
                "cash_impact_pct": 15,
                "affected_assets": ["sp500", "xlk", "eem", "omxs30"],
            })

        # 3. COT extremer
        gold_signal = features.get("gold_positioning_signal", 0)
        if gold_signal == -1:
            signals.append({
                "source": "cot_positioning",
                "signal": "GOLD_OVERCROWDED_LONG",
                "strength": "MEDIUM",
                "message": "Guldpositionering i 90+ percentil. Overcrowded — risk för reversal.",
                "action": "MINSKA_GULD_SATELLIT",
                "cash_impact_pct": 0,
                "affected_assets": ["gold", "silver"],
            })
        elif gold_signal == 1:
            signals.append({
                "source": "cot_positioning",
                "signal": "GOLD_OVERCROWDED_SHORT",
                "strength": "MEDIUM",
                "message": "Guldpositionering i 10- percentil. Kontrarian köpsignal.",
                "action": "OKA_GULD",
                "cash_impact_pct": 0,
                "affected_assets": ["gold", "silver"],
            })

        # 4. Korrelationsregim-break
        if features.get("correlation_regime_break") == 1:
            signals.append({
                "source": "correlation_regime",
                "signal": "CORRELATION_SPIKE",
                "strength": "HIGH",
                "message": "Korskorrelation stiger snabbt (>0.50, +0.10 vs 60d). Diversifiering dör. Tidig krissignal.",
                "action": "OKA_KASSA_10PCT",
                "cash_impact_pct": 10,
                "affected_assets": ["sp500", "eem", "xlk", "xle"],
            })

        # 5. Options kontrarian
        if features.get("options_contrarian_signal") == 1:
            signals.append({
                "source": "options_market",
                "signal": "EXTREME_FEAR",
                "strength": "MEDIUM",
                "message": "VIX/SMA ratio >1.3 — extrem rädsla. Historiskt: kontrarian köpsignal.",
                "action": "KONTRARIAN_KOP_SIGNAL",
                "cash_impact_pct": 0,
                "affected_assets": ["sp500", "xlk"],
            })
        elif features.get("options_contrarian_signal") == -1:
            signals.append({
                "source": "options_market",
                "signal": "EXTREME_COMPLACENCY",
                "strength": "MEDIUM",
                "message": "VIX/SMA ratio <0.75 — extrem självsäkerhet. Historiskt: varningssignal.",
                "action": "MINSKA_RISK",
                "cash_impact_pct": 3,
                "affected_assets": ["sp500", "xlk", "eem"],
            })

        logger.info(f"🚨 Direct signals: {len(signals)} active")
        return signals
