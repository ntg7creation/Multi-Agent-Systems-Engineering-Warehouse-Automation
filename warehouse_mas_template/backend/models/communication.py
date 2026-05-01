from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass
class CommunicationModule:
    messages_sent: int = 0
    messages_received: int = 0
    knowledge_updates_received: int = 0

    def exchange_with(self, owner: "Agent", other: "Agent") -> Dict[str, object]:
        owner_updates = owner.memory_module.merge_from(other.memory_module)
        other_updates = other.memory_module.merge_from(owner.memory_module)
        self.messages_sent += 1
        self.messages_received += 1
        self.knowledge_updates_received += owner_updates
        other.communication_module.messages_sent += 1
        other.communication_module.messages_received += 1
        other.communication_module.knowledge_updates_received += other_updates
        return {
            "from": owner.agent_id,
            "to": other.agent_id,
            "owner_updates": owner_updates,
            "other_updates": other_updates,
        }

    def serialize(self) -> Dict[str, int]:
        return {
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "knowledge_updates_received": self.knowledge_updates_received,
        }
