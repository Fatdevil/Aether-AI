# ============================================================
# FIL: backend/predictive/confidence_calibrator.py
# Kalibrerar systemets sannolikhetsbedömningar mot verkligheten
#
# FRÅGA: När systemet säger "70% sannolikhet", inträffar det
# verkligen 70% av gångerna? Om inte: JUSTERA.
# ============================================================

import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import json
import os
import logging

logger = logging.getLogger(__name__)

CALIBRATION_FILE = "data/confidence_calibration.json"


@dataclass
class PredictionRecord:
    prediction_id: str
    stated_probability: float
    outcome: Optional[bool]  # None = pending, True/False = evaluated
    source: str
    timestamp: str
    asset: str = ""
    predicted_score: float = 0.0  # Original signed score (-10 to +10)
    price_at_prediction: float = 0.0  # Price when prediction was made


class ConfidenceCalibrator:
    def __init__(self):
        self.records: List[PredictionRecord] = []
        self.calibration_curve: Dict[str, float] = {}
        self._load()

    def _load(self):
        try:
            from db import kv_get
            data = kv_get("confidence_calibration")
            if data:
                self._parse_records(data)
                return
        except Exception:
            pass
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE, "r") as f:
                    data = json.load(f)
                    self._parse_records(data)
            except Exception:
                pass

    def _parse_records(self, data: dict):
        """Parse records, handling old format gracefully."""
        raw_records = data.get("records", [])
        self.records = []
        poisoned_count = 0
        for r in raw_records:
            # Migrate old format: add missing fields with defaults
            r.setdefault("predicted_score", 0.0)
            r.setdefault("price_at_prediction", 0.0)
            record = PredictionRecord(**r)
            # Purge poisoned records: outcome=False with no price data = never evaluated
            if record.outcome is False and record.price_at_prediction == 0.0:
                poisoned_count += 1
                continue  # Skip poisoned data
            self.records.append(record)
        if poisoned_count > 0:
            logger.warning(f"🧹 Purged {poisoned_count} poisoned calibration records (outcome=False, no price data)")
        self.calibration_curve = data.get("curve", {})

    def _save(self):
        data = {
            "records": [
                {
                    "prediction_id": r.prediction_id,
                    "stated_probability": r.stated_probability,
                    "outcome": r.outcome,
                    "source": r.source,
                    "timestamp": r.timestamp,
                    "asset": r.asset,
                    "predicted_score": r.predicted_score,
                    "price_at_prediction": r.price_at_prediction,
                }
                for r in self.records[-5000:]
            ],
            "curve": self.calibration_curve,
        }
        try:
            from db import kv_set
            kv_set("confidence_calibration", data)
        except Exception:
            os.makedirs("data", exist_ok=True)
            with open(CALIBRATION_FILE, "w") as f:
                json.dump(data, f)

    def log_prediction(
        self,
        prediction_id: str,
        stated_prob: float,
        source: str,
        asset: str = "",
        predicted_score: float = 0.0,
        price_at_prediction: float = 0.0,
    ):
        """Log a new prediction. Outcome starts as None (pending evaluation)."""
        self.records.append(PredictionRecord(
            prediction_id=prediction_id,
            stated_probability=stated_prob,
            outcome=None,  # PENDING — will be evaluated by auto_evaluate_outcomes()
            source=source,
            timestamp=datetime.now(timezone.utc).isoformat(),
            asset=asset,
            predicted_score=predicted_score,
            price_at_prediction=price_at_prediction,
        ))
        self._save()

    def log_outcome(self, prediction_id: str, outcome: bool):
        for record in self.records:
            if record.prediction_id == prediction_id:
                record.outcome = outcome
                break
        self._save()

    def auto_evaluate_outcomes(self, current_prices: dict) -> dict:
        """Automatically evaluate pending predictions against actual price movement.
        
        Called every pipeline run. Compares predicted direction (score sign)
        with actual price change since prediction was made.
        
        Args:
            current_prices: dict of {asset_id: {"price": float, "changePct": float}}
        
        Returns:
            Summary of evaluations performed.
        """
        now = datetime.now(timezone.utc)
        evaluated = 0
        correct = 0
        skipped = 0
        
        for record in self.records:
            # Skip already evaluated
            if record.outcome is not None:
                continue
            
            # Need asset and price data
            if not record.asset or record.price_at_prediction <= 0:
                skipped += 1
                continue
            
            # Must be at least 4 hours old
            try:
                pred_time = datetime.fromisoformat(record.timestamp)
                if pred_time.tzinfo is None:
                    pred_time = pred_time.replace(tzinfo=timezone.utc)
                hours_since = (now - pred_time).total_seconds() / 3600
                if hours_since < 4:
                    continue  # Too soon to evaluate
            except (ValueError, TypeError):
                skipped += 1
                continue
            
            # Get current price for this asset
            asset_data = current_prices.get(record.asset)
            if not asset_data:
                continue
            
            current_price = asset_data.get("price", 0)
            if current_price <= 0:
                continue
            
            # Calculate actual price change since prediction
            actual_change_pct = ((current_price - record.price_at_prediction) / record.price_at_prediction) * 100
            
            # Determine if prediction was correct
            # Score > 0 = predicted UP, Score < 0 = predicted DOWN
            predicted_direction = 1 if record.predicted_score > 0 else -1 if record.predicted_score < 0 else 0
            actual_direction = 1 if actual_change_pct > 0.2 else -1 if actual_change_pct < -0.2 else 0
            
            if actual_direction == 0:
                # Very small move (±0.2%) — consider prediction "correct" (market was flat)
                record.outcome = True
            elif predicted_direction == 0:
                # We predicted neutral, market moved — incorrect
                record.outcome = False
            else:
                # Direction match?
                record.outcome = (predicted_direction == actual_direction)
            
            evaluated += 1
            if record.outcome:
                correct += 1
        
        if evaluated > 0:
            self._save()
            accuracy = correct / evaluated
            logger.info(
                f"📊 Calibration: evaluated {evaluated} predictions, "
                f"{correct}/{evaluated} correct ({accuracy:.0%})"
            )
        
        return {
            "evaluated": evaluated,
            "correct": correct,
            "accuracy": round(correct / evaluated, 3) if evaluated > 0 else 0,
            "skipped": skipped,
            "pending": sum(1 for r in self.records if r.outcome is None),
            "total_with_outcomes": sum(1 for r in self.records if r.outcome is not None),
        }

    def compute_calibration(self, n_bins: int = 10) -> Dict:
        evaluated = [r for r in self.records if r.outcome is not None]
        if len(evaluated) < 20:
            return {"status": "OTILLRÄCKLIG_DATA", "records": len(evaluated), "min_needed": 20}

        bins = {}
        for record in evaluated:
            bin_idx = min(int(record.stated_probability * n_bins), n_bins - 1)
            bin_key = f"{bin_idx * 10}-{(bin_idx + 1) * 10}%"
            if bin_key not in bins:
                bins[bin_key] = {"stated_probs": [], "outcomes": []}
            bins[bin_key]["stated_probs"].append(record.stated_probability)
            bins[bin_key]["outcomes"].append(1.0 if record.outcome else 0.0)

        calibration = {}
        for bin_key, data in sorted(bins.items()):
            n = len(data["outcomes"])
            if n < 3:
                continue
            avg_stated = float(np.mean(data["stated_probs"]))
            actual_rate = float(np.mean(data["outcomes"]))
            calibration[bin_key] = {
                "avg_stated_probability": round(avg_stated, 3),
                "actual_frequency": round(actual_rate, 3),
                "n_predictions": n,
                "gap": round(actual_rate - avg_stated, 3),
                "is_overconfident": actual_rate < avg_stated - 0.05,
                "is_underconfident": actual_rate > avg_stated + 0.05,
            }

        all_stated = np.array([r.stated_probability for r in evaluated])
        all_outcomes = np.array([1.0 if r.outcome else 0.0 for r in evaluated])
        brier_score = float(np.mean((all_stated - all_outcomes) ** 2))

        self.calibration_curve = {
            bin_key: data["actual_frequency"] / max(data["avg_stated_probability"], 0.01)
            for bin_key, data in calibration.items()
            if data["n_predictions"] >= 5
        }
        self._save()

        overconfident_bins = sum(1 for d in calibration.values() if d.get("is_overconfident"))
        underconfident_bins = sum(1 for d in calibration.values() if d.get("is_underconfident"))

        if overconfident_bins > len(calibration) * 0.6:
            diagnosis = "ÖVERKONFIDENT: Systemet överskattar sannolikheter. Skala ner ~15%."
        elif underconfident_bins > len(calibration) * 0.6:
            diagnosis = "UNDERKONFIDENT: Systemet underskattar sannolikheter. Skala upp ~10%."
        else:
            diagnosis = "RIMLIGT KALIBRERAT: Mindre justeringar kan förbättra precision."

        return {
            "total_predictions": len(evaluated),
            "brier_score": round(brier_score, 4),
            "brier_interpretation": "BRA" if brier_score < 0.15 else "MEDEL" if brier_score < 0.25 else "DÅLIG",
            "calibration_bins": calibration,
            "diagnosis": diagnosis,
            "overconfident_bins": overconfident_bins,
            "underconfident_bins": underconfident_bins,
        }

    def adjust_probability(self, raw_probability: float) -> float:
        """Adjust probability using calibration curve.
        
        GUARD: Only apply calibration if we have verified outcomes.
        Without real outcomes, the curve is poisoned (all outcome=False)
        and crushes confidence to the 0.15 floor.
        """
        # Check if we have ANY true outcomes (real evaluation data)
        true_outcomes = sum(1 for r in self.records if r.outcome is True)
        if true_outcomes < 20:
            # Not enough real data — return raw probability with basic clamping
            return max(0.15, min(0.99, raw_probability))

        if not self.calibration_curve:
            return max(0.15, min(0.99, raw_probability))

        bin_idx = min(int(raw_probability * 10), 9)
        bin_key = f"{bin_idx * 10}-{(bin_idx + 1) * 10}%"
        adjustment = self.calibration_curve.get(bin_key, 1.0)
        adjusted = raw_probability * adjustment
        return max(0.15, min(0.99, adjusted))

    def per_source_calibration(self) -> Dict:
        sources = set(r.source for r in self.records)
        per_source = {}
        for source in sources:
            source_records = [r for r in self.records if r.source == source and r.outcome is not None]
            if len(source_records) < 10:
                continue
            stated = np.array([r.stated_probability for r in source_records])
            outcomes = np.array([1.0 if r.outcome else 0.0 for r in source_records])
            brier = float(np.mean((stated - outcomes) ** 2))
            accuracy = float(np.mean((stated > 0.5).astype(float) == outcomes))
            per_source[source] = {
                "n_predictions": len(source_records),
                "brier_score": round(brier, 4),
                "accuracy": round(accuracy, 3),
                "avg_stated": round(float(np.mean(stated)), 3),
                "avg_actual": round(float(np.mean(outcomes)), 3),
                "overconfident": float(np.mean(stated)) > float(np.mean(outcomes)) + 0.05
            }
        return per_source
