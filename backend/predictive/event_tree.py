# ============================================================
# FIL: backend/predictive/event_tree.py
# Event-sannolikhetsträd: förgrenade scenarier med kumulativa
# sannolikheter och portföljeffekter per blad
#
# Skiljer sig från CausalChain:
# - CausalChain: EN väg med länkar (A → B → C)
# - EventTree: FÖRGRENADE vägar (A → B1/B2 → C1/C2/C3)
#
# Nyckelbegrepp:
# - Konvex position: Tjänar oavsett vilken gren som inträffar
# ============================================================

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)

TREE_FILE = "data/event_trees.json"


@dataclass
class TreeNode:
    """En nod i event-trädet"""
    id: str
    event: str
    probability: float
    time_horizon_days: int
    asset_impacts: Dict[str, float]
    children: List['TreeNode'] = field(default_factory=list)
    is_leaf: bool = False
    monitoring_signal: str = ""
    confidence: str = "MEDIUM"


@dataclass
class EventTree:
    """Ett komplett event-träd"""
    id: str
    name: str
    root_event: str
    created_at: str
    root: TreeNode
    total_scenarios: int
    expected_portfolio_impact: Dict[str, float]
    convex_positions: List[Dict]
    status: str = "ACTIVE"


class EventTreeEngine:
    """
    Bygger och analyserar event-sannolikhetsträd.

    Workflow:
    1. Definiera rot-händelse
    2. AI bygger trädet med förgreningar
    3. Beräkna sannolikhetsviktad portföljeffekt
    4. Identifiera konvexa positioner
    5. Övervaka bevakningssignaler
    """

    def __init__(self):
        self.trees: List[EventTree] = []
        self._load()

    def _load(self):
        if os.path.exists(TREE_FILE):
            try:
                with open(TREE_FILE, "r") as f:
                    data = json.load(f)
                    # Trees are complex nested structures — load as raw dicts
                    for tree_data in data.get("trees", []):
                        try:
                            root = self._parse_node_dict(tree_data.get("root", {}))
                            leaves = self._get_leaves(root)
                            tree = EventTree(
                                id=tree_data.get("id", ""),
                                name=tree_data.get("name", ""),
                                root_event=tree_data.get("root_event", ""),
                                created_at=tree_data.get("created_at", ""),
                                root=root,
                                total_scenarios=len(leaves),
                                expected_portfolio_impact=tree_data.get("expected_portfolio_impact", {}),
                                convex_positions=tree_data.get("convex_positions", []),
                                status=tree_data.get("status", "ACTIVE")
                            )
                            self.trees.append(tree)
                        except Exception:
                            pass
            except Exception:
                pass

    def _parse_node_dict(self, d: Dict) -> TreeNode:
        """Recursively parse a dict into TreeNode"""
        children = [self._parse_node_dict(c) for c in d.get("children", [])]
        return TreeNode(
            id=d.get("id", ""),
            event=d.get("event", ""),
            probability=float(d.get("probability", 1.0)),
            time_horizon_days=int(d.get("time_horizon_days", 14)),
            asset_impacts=d.get("asset_impacts", {}),
            children=children,
            is_leaf=len(children) == 0,
            monitoring_signal=d.get("monitoring_signal", ""),
            confidence=d.get("confidence", "MEDIUM")
        )

    def _save(self):
        os.makedirs(os.path.dirname(TREE_FILE), exist_ok=True)
        with open(TREE_FILE, "w") as f:
            json.dump({"trees": [asdict(t) for t in self.trees[-50:]]}, f, default=str)

    def build_tree_prompt(self, event: str, context: str = "") -> str:
        """Genererar prompt för AI att bygga ett event-träd"""
        return f"""Du är en scenarioanalytiker som bygger sannolikhetsträd.
Givet en händelse, bygg ett träd med 2-3 förgreningsnivåer och 4-8 slutscenarier.

HÄNDELSE: {event}
{"KONTEXT: " + context if context else ""}

Svara ENBART med JSON:
{{
    "name": "Kort namn för trädet",
    "root_event": "{event}",
    "tree": {{
        "event": "Nuvarande situation",
        "branches": [
            {{
                "event": "Scenario A (t.ex. eskalering)",
                "probability": 0.40,
                "time_days": 14,
                "asset_impacts": {{"OIL": 10, "GOLD": 5, "SP500": -3}},
                "monitoring_signal": "Vad att bevaka",
                "branches": [
                    {{
                        "event": "A1: Vidare eskalering",
                        "probability": 0.50,
                        "time_days": 30,
                        "asset_impacts": {{"OIL": 25, "GOLD": 12, "SP500": -8}},
                        "monitoring_signal": "Signal",
                        "branches": []
                    }}
                ]
            }},
            {{
                "event": "Scenario B (status quo)",
                "probability": 0.35,
                "time_days": 30,
                "asset_impacts": {{"OIL": -2, "GOLD": 0, "SP500": 2}},
                "monitoring_signal": "Signal",
                "branches": []
            }},
            {{
                "event": "Scenario C (de-eskalering)",
                "probability": 0.25,
                "time_days": 21,
                "asset_impacts": {{"OIL": -15, "GOLD": -5, "SP500": 8}},
                "monitoring_signal": "Signal",
                "branches": []
            }}
        ]
    }}
}}

REGLER:
- Sannolikheter på samma nivå MÅSTE summera till 1.0
- Minst 3 grenar på rotnivån
- Minst 4 slutscenarier totalt
- asset_impacts i PROCENT
- Var SPECIFIK med tillgångar (OIL, GOLD, SP500, BTC, USDSEK etc)
- BARA JSON"""

    def parse_tree_response(self, response: Dict) -> EventTree:
        """Parsar AI-svar till EventTree"""

        def parse_node(data: Dict, depth: int = 0) -> TreeNode:
            node_id = f"node_{depth}_{hash(data.get('event', '')) % 10000}"
            children = []
            branches = data.get("branches", [])

            for branch in branches:
                child = parse_node(branch, depth + 1)
                children.append(child)

            return TreeNode(
                id=node_id,
                event=data.get("event", ""),
                probability=float(data.get("probability", 1.0 if depth == 0 else 0.5)),
                time_horizon_days=int(data.get("time_days", 14)),
                asset_impacts=data.get("asset_impacts", {}),
                children=children,
                is_leaf=len(children) == 0,
                monitoring_signal=data.get("monitoring_signal", ""),
                confidence=data.get("confidence", "MEDIUM")
            )

        tree_data = response.get("tree", response)
        root = parse_node(tree_data)

        leaves = self._get_leaves(root)
        expected_impact = self._calculate_expected_impact(root)
        convex = self._find_convex_positions(leaves)

        tree = EventTree(
            id=f"tree_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            name=response.get("name", "Unnamed"),
            root_event=response.get("root_event", ""),
            created_at=datetime.now().isoformat(),
            root=root,
            total_scenarios=len(leaves),
            expected_portfolio_impact=expected_impact,
            convex_positions=convex,
        )

        self.trees.append(tree)
        self._save()
        return tree

    def _get_leaves(self, node: TreeNode, path_prob: float = 1.0) -> List[Tuple[TreeNode, float]]:
        """Hämta alla blad med kumulativ sannolikhet"""
        current_prob = path_prob * node.probability

        if node.is_leaf or not node.children:
            return [(node, current_prob)]

        leaves = []
        for child in node.children:
            leaves.extend(self._get_leaves(child, current_prob))
        return leaves

    def _calculate_expected_impact(self, root: TreeNode) -> Dict[str, float]:
        """Sannolikhetsviktad påverkan per tillgång över alla blad"""
        leaves = self._get_leaves(root)
        impacts = {}

        for leaf, prob in leaves:
            for asset, impact in leaf.asset_impacts.items():
                if asset not in impacts:
                    impacts[asset] = 0
                impacts[asset] += impact * prob

        return {k: round(v, 2) for k, v in impacts.items()}

    def _find_convex_positions(self, leaves: List[Tuple[TreeNode, float]]) -> List[Dict]:
        """
        Hitta positioner som tjänar i de flesta scenarier.
        KONVEXITET: En position som vinner mer när den vinner
        än den förlorar när den förlorar.
        """
        if not leaves:
            return []

        all_assets = set()
        for leaf, _ in leaves:
            all_assets.update(leaf.asset_impacts.keys())

        convex = []
        for asset in all_assets:
            positive_scenarios = 0
            negative_scenarios = 0
            total_positive_impact = 0
            total_negative_impact = 0
            weighted_sum = 0

            for leaf, prob in leaves:
                impact = leaf.asset_impacts.get(asset, 0)
                weighted_sum += impact * prob

                if impact > 0:
                    positive_scenarios += 1
                    total_positive_impact += impact * prob
                elif impact < 0:
                    negative_scenarios += 1
                    total_negative_impact += abs(impact) * prob

            total_scenarios = len(leaves)
            win_ratio = positive_scenarios / max(total_scenarios, 1)
            asymmetry = total_positive_impact / max(total_negative_impact, 0.01)

            if win_ratio > 0.6 or (win_ratio > 0.4 and asymmetry > 2.0):
                convex.append({
                    "asset": asset,
                    "direction": "LONG" if weighted_sum > 0 else "SHORT",
                    "win_ratio": round(win_ratio, 2),
                    "asymmetry": round(asymmetry, 2),
                    "expected_impact": round(weighted_sum, 2),
                    "positive_scenarios": positive_scenarios,
                    "total_scenarios": total_scenarios,
                    "reasoning": f"Positiv i {positive_scenarios}/{total_scenarios} scenarier. "
                                 f"Asymmetri {asymmetry:.1f}x (vinner mer än förlorar)."
                })

        convex.sort(key=lambda x: x["asymmetry"] * x["win_ratio"], reverse=True)
        return convex

    def get_all_convex_positions(self) -> List[Dict]:
        """Aggregera konvexa positioner över ALLA aktiva träd"""
        all_convex = {}

        for tree in self.trees:
            if tree.status != "ACTIVE":
                continue
            for pos in tree.convex_positions:
                asset = pos["asset"]
                if asset not in all_convex:
                    all_convex[asset] = {
                        "asset": asset,
                        "supporting_trees": 0,
                        "avg_win_ratio": 0,
                        "avg_asymmetry": 0,
                        "total_expected_impact": 0,
                        "directions": []
                    }
                all_convex[asset]["supporting_trees"] += 1
                all_convex[asset]["avg_win_ratio"] += pos["win_ratio"]
                all_convex[asset]["avg_asymmetry"] += pos["asymmetry"]
                all_convex[asset]["total_expected_impact"] += pos["expected_impact"]
                all_convex[asset]["directions"].append(pos["direction"])

        for asset, data in all_convex.items():
            n = data["supporting_trees"]
            data["avg_win_ratio"] = round(data["avg_win_ratio"] / n, 2)
            data["avg_asymmetry"] = round(data["avg_asymmetry"] / n, 2)
            data["consensus_direction"] = max(set(data["directions"]), key=data["directions"].count)
            del data["directions"]

        sorted_convex = sorted(
            all_convex.values(),
            key=lambda x: x["supporting_trees"] * x["avg_asymmetry"],
            reverse=True
        )

        return sorted_convex
