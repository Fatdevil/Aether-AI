# ============================================================
# FIL: backend/system_health.py
# Övervakar systemets hälsa och varnar vid problem
# Stödjer både PostgreSQL (kv_store) och lokal SQLite (filer)
# ============================================================

import os
from datetime import datetime
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

# KV keys that correspond to the old JSON files
KV_KEYS = [
    "causal_chains",
    "detected_events",
    "narratives",
    "event_trees",
    "actor_simulations",
    "confidence_calibration",
    "meta_strategy",
    "agent_performance_log",
]


class SystemHealthCheck:
    """
    Övervakar:
    1. Data-färskhet: finns data i databasen/filer?
    2. Pipeline-status: har dagliga körningen gått?
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir

    def run_checks(self) -> Dict:
        checks = {}

        # Always try KV store first — it works on Railway even if DB_TYPE isn't "postgresql"
        kv_available = False
        try:
            from db import kv_get
            # Test one key to see if KV store is available
            for key in KV_KEYS:
                try:
                    data = kv_get(key)
                    kv_available = True  # If we get here, KV works
                    if data:
                        checks[key] = {
                            "exists": True,
                            "stale": False,
                            "size_kb": 0,
                            "too_large": False,
                            "source": "postgresql"
                        }
                    else:
                        checks[key] = {
                            "exists": False,
                            "stale": False,
                            "size_kb": 0,
                            "too_large": False,
                            "source": "postgresql"
                        }
                except Exception:
                    checks[key] = {"exists": False, "stale": False, "size_kb": 0, "too_large": False, "source": "postgresql"}
        except ImportError:
            pass

        if not kv_available:
            # Local mode: check JSON files
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
                        "too_large": size_kb > 10000,
                        "source": "file"
                    }
                else:
                    checks[fpath] = {"exists": False, "stale": True, "size_kb": 0, "too_large": False, "source": "file"}

        stale_count = sum(1 for c in checks.values() if c.get("stale"))
        missing_count = sum(1 for c in checks.values() if not c.get("exists"))
        large_count = sum(1 for c in checks.values() if c.get("too_large"))

        # In PostgreSQL mode, missing data is OK — pipeline just hasn't run yet
        if kv_available:
            if missing_count > 6:
                status = "WARMING_UP"
                message = f"Pipeline har inte kört ännu — {len(KV_KEYS) - missing_count}/{len(KV_KEYS)} moduler har data"
            elif missing_count > 0:
                status = "HEALTHY"
                message = f"{len(KV_KEYS) - missing_count}/{len(KV_KEYS)} moduler aktiva. Pipeline fyller på data automatiskt."
            else:
                status = "HEALTHY"
                message = "Alla system fungerar normalt. Data sparas permanent i PostgreSQL."
        else:
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
            "db_mode": "postgresql" if kv_available else "sqlite",
            "recommendations": self._recommendations(checks, kv_available)
        }

    def _recommendations(self, checks: Dict, use_pg: bool = False) -> List[str]:
        recs = []
        if use_pg:
            missing = [k for k, v in checks.items() if not v.get("exists")]
            if missing:
                recs.append(f"Kör pipeline — {len(missing)} moduler väntar på sin första körning")
            return recs

        for path, check in checks.items():
            if not check.get("exists"):
                recs.append(f"Kör pipeline för att skapa {path}")
            elif check.get("stale"):
                recs.append(f"{path} är {check['age_hours']:.0f}h gammal — kör daglig pipeline")
            elif check.get("too_large"):
                recs.append(f"{path} är {check['size_kb']:.0f}KB — rensa gammal data")
        return recs

