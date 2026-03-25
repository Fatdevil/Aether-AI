# ============================================================
# FIL: backend/system_health.py
# Övervakar systemets hälsa och varnar vid problem
# ============================================================

import os
from datetime import datetime
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)


class SystemHealthCheck:
    """
    Övervakar:
    1. Data-färskhet: är datafiler uppdaterade?
    2. Filstorlek: växer loggfiler för snabbt?
    3. Pipeline-status: har dagliga körningen gått?
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir

    def run_checks(self) -> Dict:
        checks = {}

        critical_files = [
            "data/causal_chains.json",
            "data/detected_events.json",
            "data/narratives.json",
            "data/event_trees.json",
            "data/actor_simulations.json",
            "data/confidence_calibration.json",
            "data/meta_strategy.json",
            "data/agent_performance_log.json",
        ]

        for fpath in critical_files:
            if os.path.exists(fpath):
                mod_time = datetime.fromtimestamp(os.path.getmtime(fpath))
                age_hours = (datetime.now() - mod_time).total_seconds() / 3600
                size_kb = os.path.getsize(fpath) / 1024
                checks[fpath] = {
                    "exists": True,
                    "age_hours": round(age_hours, 1),
                    "size_kb": round(size_kb, 1),
                    "stale": age_hours > 48,
                    "too_large": size_kb > 10000
                }
            else:
                checks[fpath] = {"exists": False, "stale": True, "size_kb": 0, "too_large": False}

        stale_count = sum(1 for c in checks.values() if c.get("stale"))
        missing_count = sum(1 for c in checks.values() if not c.get("exists"))
        large_count = sum(1 for c in checks.values() if c.get("too_large"))

        if missing_count > 4 or stale_count > 5:
            status = "UNHEALTHY"
            message = f"{missing_count} saknade, {stale_count} inaktuella filer"
        elif stale_count > 2 or large_count > 0 or missing_count > 2:
            status = "WARNING"
            message = f"{stale_count} filer behöver uppdateras, {large_count} för stora"
        else:
            status = "HEALTHY"
            message = "Alla system fungerar normalt"

        return {
            "status": status,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "file_checks": checks,
            "stale_files": stale_count,
            "missing_files": missing_count,
            "recommendations": self._recommendations(checks)
        }

    def _recommendations(self, checks: Dict) -> List[str]:
        recs = []
        for path, check in checks.items():
            if not check.get("exists"):
                recs.append(f"Kör pipeline för att skapa {path}")
            elif check.get("stale"):
                recs.append(f"{path} är {check['age_hours']:.0f}h gammal — kör daglig pipeline")
            elif check.get("too_large"):
                recs.append(f"{path} är {check['size_kb']:.0f}KB — rensa gammal data")
        return recs
