# ============================================================
# FIL: backend/predictive/confidence_calibrator.py
# Kalibrerar systemets sannolikhetsbedömningar mot verkligheten
#
# FRÅGA: När systemet säger "70% sannolikhet", inträffar det
# verkligen 70% av gångerna? Om inte: JUSTERA.
# ============================================================

import numpy as np
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime
import json
import os
import logging

logger = logging.getLogger(__name__)

CALIBRATION_FILE = "data/confidence_calibration.json"


@dataclass
class PredictionRecord:
    prediction_id: str
    stated_probability: float
    outcome: bool
    source: str
    timestamp: str
    asset: str = ""


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
                self.records = [PredictionRecord(**r) for r in data.get("records", [])]
                self.calibration_curve = data.get("curve", {})
                return
        except Exception:
            pass
        if os.path.exists(CALIBRATION_FILE):
            try:
                with open(CALIBRATION_FILE, "r") as f:
                    data = json.load(f)
                    self.records = [PredictionRecord(**r) for r in data.get("records", [])]
                    self.calibration_curve = data.get("curve", {})
            except Exception:
                pass

    def _save(self):
        data = {
            "records": [{"prediction_id": r.prediction_id, "stated_probability": r.stated_probability,
                        "outcome": r.outcome, "source": r.source, "timestamp": r.timestamp, "asset": r.asset}
                       for r in self.records[-5000:]],
            "curve": self.calibration_curve
        }
        try:
            from db import kv_set
            kv_set("confidence_calibration", data)
        except Exception:
            os.makedirs("data", exist_ok=True)
            with open(CALIBRATION_FILE, "w") as f:
                json.dump(data, f)

    def log_prediction(self, prediction_id: str, stated_prob: float, source: str, asset: str = ""):
        self.records.append(PredictionRecord(
            prediction_id=prediction_id,
            stated_probability=stated_prob,
            outcome=False,
            source=source,
            timestamp=datetime.now().isoformat(),
            asset=asset
        ))
        self._save()

    def log_outcome(self, prediction_id: str, outcome: bool):
        for record in self.records:
            if record.prediction_id == prediction_id:
                record.outcome = outcome
                break
        self._save()

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
        if not self.calibration_curve:
            return raw_probability
        bin_idx = min(int(raw_probability * 10), 9)
        bin_key = f"{bin_idx * 10}-{(bin_idx + 1) * 10}%"
        adjustment = self.calibration_curve.get(bin_key, 1.0)
        adjusted = raw_probability * adjustment
        return max(0.01, min(0.99, adjusted))

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
