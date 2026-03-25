# ============================================================
# FIL: backend/domain_knowledge.py
# Tar emot användarens insikter och injicerar i alla agenter
# ============================================================

from typing import Dict, List, Optional
from datetime import datetime


class DomainKnowledgeManager:
    """
    Hanterar användarinmatade insikter som skickas till alla AI-agenter.
    Exempel: "Hormuz öppnas partiellt enl läckta rapporter"
    """

    def __init__(self):
        self.notes: List[Dict] = []

    def add_note(self, text: str, category: str = "general", priority: int = 5) -> Dict:
        """
        Lägg till en användarnotering.
        category: "geopolitik", "sektor", "foretag", "teknisk", "general"
        priority: 1-10 (10 = extremt viktigt)
        """
        note = {
            "id": len(self.notes),
            "text": text,
            "category": category,
            "priority": priority,
            "timestamp": datetime.now().isoformat(),
            "active": True
        }
        self.notes.append(note)
        return note

    def remove_note(self, note_id: int):
        for note in self.notes:
            if note["id"] == note_id:
                note["active"] = False

    def get_active_notes(self) -> List[Dict]:
        return [n for n in self.notes if n["active"]]

    def build_agent_context(self) -> str:
        """
        Bygg kontext-sträng att injicera i alla agent-prompts.
        Hög-prioritets-noter först.
        """
        active = self.get_active_notes()
        if not active:
            return ""

        active.sort(key=lambda x: x["priority"], reverse=True)

        lines = ["\n--- ANVÄNDARE DOMÄNKUNSKAP ---"]
        for note in active:
            prio_tag = "⚠️ KRITISKT" if note["priority"] >= 8 else "❗ VIKTIGT" if note["priority"] >= 5 else "📝 NOTERING"
            lines.append(f"[{prio_tag}] [{note['category'].upper()}] {note['text']}")
        lines.append("--- SLUT DOMÄNKUNSKAP ---\n")

        return "\n".join(lines)

    def inject_into_agent_prompt(self, base_prompt: str) -> str:
        """Lägg till domänkunskap i en agents system-prompt"""
        context = self.build_agent_context()
        if not context:
            return base_prompt
        return base_prompt + "\n" + context
