"""
Trade Signal Generator - Converts AI scores into actionable trade signals.
Provides entry/exit levels, ATR-based stop-loss, position sizing, and risk/reward ratios.
Uses technical indicators and AI analysis to generate specific, actionable trade levels.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("aether.signals")


class TradeSignalGenerator:
    """Generates actionable trade signals from AI analysis + technical indicators."""

    def generate_signal(self, asset_id: str, analysis: dict, price_data: dict) -> dict:
        """
        Generate a complete trade signal for an asset.
        
        Args:
            asset_id: e.g. "btc"
            analysis: The AI analysis result (with finalScore, recommendation, etc.)
            price_data: Current price data (with indicators)
        
        Returns:
            Complete trade signal with entry, stop-loss, targets, position sizing.
        """
        indicators = price_data.get("indicators", {})
        current_price = price_data.get("price", 0)
        score = analysis.get("finalScore", 0)
        confidence = analysis.get("supervisorConfidence", 0.5)
        recommendation = analysis.get("recommendation", "Neutral")

        if not current_price or current_price <= 0:
            return self._empty_signal(asset_id, "Ingen prisdata")

        # ATR for volatility-based levels
        atr = indicators.get("atr_14", current_price * 0.02)  # Fallback: 2%
        atr_pct = indicators.get("atr_pct", 2.0)

        # Determine signal direction and strength
        direction = self._get_direction(score, recommendation)
        strength = self._get_strength(abs(score), confidence)

        if direction == "neutral":
            return self._neutral_signal(asset_id, current_price, atr, score, confidence, indicators)

        # === ENTRY LEVELS ===
        entry = self._calculate_entry(direction, current_price, atr, indicators)

        # === STOP-LOSS (ATR-based) ===
        stop_loss = self._calculate_stop_loss(direction, entry["primary"], atr, strength)

        # === PROFIT TARGETS (multiple) ===
        targets = self._calculate_targets(direction, entry["primary"], atr, strength, indicators)

        # === RISK/REWARD RATIO ===
        risk = abs(entry["primary"] - stop_loss["price"])
        reward_t1 = abs(targets[0]["price"] - entry["primary"]) if targets else 0
        reward_t2 = abs(targets[1]["price"] - entry["primary"]) if len(targets) > 1 else reward_t1
        rr_ratio = round(reward_t1 / risk, 2) if risk > 0 else 0

        # === POSITION SIZING ===
        position = self._calculate_position_size(current_price, stop_loss["price"], atr_pct)

        # === SIGNAL QUALITY ===
        quality = self._assess_quality(score, confidence, rr_ratio, indicators)

        return {
            "asset_id": asset_id,
            "direction": direction,
            "strength": strength,
            "score": score,
            "confidence": confidence,
            "recommendation": recommendation,
            "current_price": current_price,
            "entry": entry,
            "stop_loss": stop_loss,
            "targets": targets,
            "risk_reward": {
                "ratio": rr_ratio,
                "risk_amount": round(risk, 2),
                "reward_t1": round(reward_t1, 2),
                "reward_t2": round(reward_t2, 2),
                "label": self._rr_label(rr_ratio),
            },
            "position_sizing": position,
            "quality": quality,
            "atr": round(atr, 2),
            "atr_pct": round(atr_pct, 2),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # ==================== DIRECTION ====================

    @staticmethod
    def _get_direction(score: float, recommendation: str) -> str:
        if score >= 3 or recommendation in ("Starkt Köp", "Köp"):
            return "long"
        elif score <= -3 or recommendation in ("Starkt Sälj", "Sälj"):
            return "short"
        return "neutral"

    @staticmethod
    def _get_strength(abs_score: float, confidence: float) -> str:
        combined = abs_score * confidence
        if combined >= 6:
            return "stark"
        elif combined >= 3:
            return "måttlig"
        return "svag"

    # ==================== ENTRY ====================

    def _calculate_entry(self, direction: str, price: float, atr: float,
                         indicators: dict) -> dict:
        """Calculate entry levels using Bollinger / SMA support/resistance."""
        bb = indicators.get("bollinger", {})
        sma_20 = indicators.get("sma_20")

        if direction == "long":
            # Primary: current price or slight pullback
            primary = price
            # Ideal: near lower Bollinger or SMA20
            ideal = bb.get("lower", price - atr * 0.5)
            if sma_20 and sma_20 < price:
                ideal = max(ideal, sma_20)  # Don't go below SMA20 if price is above
            # Aggressive: market price now
            aggressive = price
        else:  # short
            primary = price
            ideal = bb.get("upper", price + atr * 0.5)
            if sma_20 and sma_20 > price:
                ideal = min(ideal, sma_20)
            aggressive = price

        return {
            "primary": round(primary, 2),
            "ideal": round(ideal, 2),
            "aggressive": round(aggressive, 2),
            "note": self._entry_note(direction, price, ideal, indicators),
        }

    @staticmethod
    def _entry_note(direction: str, price: float, ideal: float, indicators: dict) -> str:
        rsi = indicators.get("rsi_14", 50)
        if direction == "long":
            if rsi < 35:
                return "RSI översålt – bra entry-zon"
            elif rsi > 65:
                return "RSI högt – vänta på pullback för bättre entry"
            return "Neutral RSI – entry vid stöd rekommenderas"
        else:
            if rsi > 65:
                return "RSI överköpt – bra short-entry"
            elif rsi < 35:
                return "RSI lågt – vänta på bounce för bättre short-entry"
            return "Neutral RSI – entry vid motstånd rekommenderas"

    # ==================== STOP-LOSS ====================

    def _calculate_stop_loss(self, direction: str, entry: float, atr: float,
                             strength: str) -> dict:
        """ATR-based stop-loss. Tighter for strong signals, wider for weak."""
        # Multiplier: strong=1.0 ATR, moderate=1.5 ATR, weak=2.0 ATR
        multipliers = {"stark": 1.0, "måttlig": 1.5, "svag": 2.0}
        mult = multipliers.get(strength, 1.5)

        if direction == "long":
            sl_price = entry - (atr * mult)
        else:
            sl_price = entry + (atr * mult)

        sl_pct = abs((sl_price - entry) / entry) * 100

        return {
            "price": round(sl_price, 2),
            "pct_from_entry": round(sl_pct, 2),
            "atr_multiple": mult,
            "type": f"ATR × {mult:.1f}",
        }

    # ==================== TARGETS ====================

    def _calculate_targets(self, direction: str, entry: float, atr: float,
                           strength: str, indicators: dict) -> list[dict]:
        """Calculate 3 profit targets at 1x, 2x, 3x ATR from entry."""
        sma_50 = indicators.get("sma_50")
        sma_200 = indicators.get("sma_200")
        bb = indicators.get("bollinger", {})

        targets = []
        for i, (mult, label) in enumerate([(1.5, "T1 (konservativ)"),
                                            (3.0, "T2 (standard)"),
                                            (5.0, "T3 (aggressiv)")]):
            if direction == "long":
                t_price = entry + (atr * mult)
                # Check if SMA resistance is closer
                if sma_50 and sma_50 > entry and sma_50 < t_price and i == 0:
                    t_price = sma_50  # Target = SMA50 resistance
                    label = "T1 (SMA50 motstånd)"
            else:
                t_price = entry - (atr * mult)
                if sma_50 and sma_50 < entry and sma_50 > t_price and i == 0:
                    t_price = sma_50
                    label = "T1 (SMA50 stöd)"

            t_pct = abs((t_price - entry) / entry) * 100
            targets.append({
                "label": label,
                "price": round(t_price, 2),
                "pct_from_entry": round(t_pct, 2),
                "atr_multiple": mult,
            })

        return targets

    # ==================== POSITION SIZING ====================

    @staticmethod
    def _calculate_position_size(price: float, stop_loss: float,
                                  atr_pct: float) -> dict:
        """Calculate position size based on risk management rules."""
        risk_per_trade_pct = 2.0  # Max 2% portfolio risk per trade
        sl_distance_pct = abs((price - stop_loss) / price) * 100

        if sl_distance_pct > 0:
            # Position size = (risk budget) / (stop-loss distance)
            max_position_pct = round(risk_per_trade_pct / sl_distance_pct * 100, 1)
        else:
            max_position_pct = 100

        # Cap at reasonable levels
        max_position_pct = min(max_position_pct, 95)

        # Volatility warning
        if atr_pct > 5:
            vol_warning = "⚠️ Extremt volatil – överväg halverad position"
            max_position_pct = min(max_position_pct, 30)
        elif atr_pct > 3:
            vol_warning = "Hög volatilitet – var försiktig med storlek"
        else:
            vol_warning = None

        return {
            "max_portfolio_pct": max_position_pct,
            "risk_per_trade_pct": risk_per_trade_pct,
            "sl_distance_pct": round(sl_distance_pct, 2),
            "volatility_warning": vol_warning,
        }

    # ==================== QUALITY ====================

    def _assess_quality(self, score: float, confidence: float,
                        rr_ratio: float, indicators: dict) -> dict:
        """Rate overall signal quality 1-5 stars."""
        points = 0

        # Strong conviction (score + confidence)
        if abs(score) >= 5 and confidence >= 0.7:
            points += 2
        elif abs(score) >= 3:
            points += 1

        # Good risk/reward
        if rr_ratio >= 3:
            points += 2
        elif rr_ratio >= 2:
            points += 1

        # Technical alignment
        rsi = indicators.get("rsi_14", 50)
        macd = indicators.get("macd", {})
        trend = indicators.get("trend", "neutral")

        if score > 0 and trend == "bullish":
            points += 1  # Trend agrees with signal
        elif score < 0 and trend == "bearish":
            points += 1

        if score > 0 and rsi < 40:
            points += 1  # Oversold + buy signal = great
        elif score < 0 and rsi > 60:
            points += 1  # Overbought + sell signal = great

        stars = min(5, max(1, points))
        labels = {5: "Exceptionell", 4: "Stark", 3: "Bra", 2: "Medel", 1: "Svag"}

        return {
            "stars": stars,
            "label": labels[stars],
            "factors": self._quality_factors(score, confidence, rr_ratio, indicators),
        }

    @staticmethod
    def _quality_factors(score, confidence, rr, indicators) -> list[str]:
        factors = []
        if abs(score) >= 5:
            factors.append("✅ Stark AI-signal")
        if confidence >= 0.75:
            factors.append("✅ Hög confidence")
        if rr >= 2.5:
            factors.append(f"✅ Bra R:R ({rr:.1f}x)")
        rsi = indicators.get("rsi_14", 50)
        if rsi < 30 or rsi > 70:
            factors.append(f"✅ RSI extremt ({rsi:.0f})")
        trend = indicators.get("trend", "")
        if trend in ("bullish", "bearish"):
            factors.append(f"✅ Tydlig trend ({trend})")
        macd = indicators.get("macd", {})
        if macd.get("crossover") in ("bullish_cross", "bearish_cross"):
            factors.append(f"✅ MACD crossover")
        if not factors:
            factors.append("⚠️ Inga starka bekräftande signaler")
        return factors

    @staticmethod
    def _rr_label(ratio: float) -> str:
        if ratio >= 3:
            return "Utmärkt"
        elif ratio >= 2:
            return "Bra"
        elif ratio >= 1.5:
            return "Acceptabel"
        elif ratio >= 1:
            return "Låg"
        return "Ofördelaktig"

    # ==================== HELPERS ====================

    def _neutral_signal(self, asset_id, price, atr, score, confidence, indicators) -> dict:
        """Signal for neutral/hold – still provide key levels."""
        bb = indicators.get("bollinger", {})
        sma_20 = indicators.get("sma_20")

        support = bb.get("lower", price - atr)
        resistance = bb.get("upper", price + atr)

        return {
            "asset_id": asset_id,
            "direction": "neutral",
            "strength": "ingen",
            "score": score,
            "confidence": confidence,
            "recommendation": "Avvakta",
            "current_price": price,
            "entry": None,
            "stop_loss": None,
            "targets": None,
            "risk_reward": None,
            "position_sizing": None,
            "quality": {"stars": 0, "label": "Ingen signal", "factors": ["Neutral – avvakta"]},
            "key_levels": {
                "support": round(support, 2),
                "resistance": round(resistance, 2),
                "sma_20": round(sma_20, 2) if sma_20 else None,
            },
            "atr": round(atr, 2),
            "atr_pct": indicators.get("atr_pct", 0),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _empty_signal(asset_id, reason):
        return {
            "asset_id": asset_id,
            "direction": "none",
            "strength": "none",
            "reason": reason,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


def format_signal_for_prompt(signal: dict) -> str:
    """Format a trade signal as text for injection into prompts/display."""
    if not signal or signal.get("direction") == "none":
        return ""

    if signal["direction"] == "neutral":
        levels = signal.get("key_levels", {})
        return (
            f"TRADE SIGNAL: AVVAKTA (score: {signal['score']:+.1f})\n"
            f"  Stöd: {levels.get('support', '?')}\n"
            f"  Motstånd: {levels.get('resistance', '?')}"
        )

    d = "LONG (KÖP)" if signal["direction"] == "long" else "SHORT (SÄLJ)"
    entry = signal["entry"]
    sl = signal["stop_loss"]
    targets = signal["targets"]
    rr = signal["risk_reward"]
    quality = signal["quality"]
    pos = signal["position_sizing"]

    lines = [
        f"TRADE SIGNAL: {d} – {signal['strength'].upper()}",
        f"  ⭐ Kvalitet: {'⭐' * quality['stars']} {quality['label']}",
        f"  Entry: {entry['primary']:,.2f} (ideal: {entry['ideal']:,.2f})",
        f"  Stop-Loss: {sl['price']:,.2f} ({sl['type']}, -{sl['pct_from_entry']:.1f}%)",
    ]
    for t in targets:
        lines.append(f"  {t['label']}: {t['price']:,.2f} (+{t['pct_from_entry']:.1f}%)")
    lines.append(f"  Risk/Reward: {rr['ratio']:.1f}x ({rr['label']})")
    lines.append(f"  Position: max {pos['max_portfolio_pct']:.0f}% av portfölj")
    if pos.get("volatility_warning"):
        lines.append(f"  {pos['volatility_warning']}")
    lines.append(f"  Faktorer: {', '.join(quality['factors'])}")

    return "\n".join(lines)


# Singleton
signal_generator = TradeSignalGenerator()
