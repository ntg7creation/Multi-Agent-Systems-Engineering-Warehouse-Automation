from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


INFORM_MAP_UPDATE = "INFORM_MAP_UPDATE"
INFORM_CURRENT_TASK = "INFORM_CURRENT_TASK"
INFORM_CURRENT_TARGET = "INFORM_CURRENT_TARGET"
ACCEPT_UPDATE = "ACCEPT_UPDATE"
REJECT_UPDATE = "REJECT_UPDATE"
CONFIRM_UPDATE = "CONFIRM_UPDATE"


@dataclass
class AgentMessage:
    performative: str
    sender_id: str
    receiver_id: str
    tick: int
    content: Dict[str, object]

    def serialize(self) -> Dict[str, object]:
        return {
            "performative": self.performative,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "tick": self.tick,
            "content": self.content,
        }


@dataclass
class CommunicationModule:
    messages_sent: int = 0
    messages_received: int = 0
    knowledge_updates_received: int = 0
    accepted_updates: int = 0
    rejected_updates: int = 0
    last_messages: List[Dict[str, object]] = field(default_factory=list)

    def exchange_with(self, owner: "Agent", other: "Agent", tick: int) -> Dict[str, object]:
        owner_messages = self._outgoing_messages(owner, other, tick)
        other_messages = other.communication_module._outgoing_messages(other, owner, tick)

        owner_results = [self.receive(owner, message) for message in other_messages]
        other_results = [other.communication_module.receive(other, message) for message in owner_messages]
        owner_updates = sum(result["accepted"] for result in owner_results)
        other_updates = sum(result["accepted"] for result in other_results)
        return {
            "from": owner.agent_id,
            "to": other.agent_id,
            "owner_updates": owner_updates,
            "other_updates": other_updates,
            "messages": [
                *(message.serialize() for message in owner_messages),
                *(message.serialize() for message in other_messages),
            ],
            "responses": [*owner_results, *other_results],
        }

    def receive(self, owner: "Agent", message: AgentMessage) -> Dict[str, object]:
        self.messages_received += 1
        accepted = 0
        rejected = 0
        if message.performative == INFORM_MAP_UPDATE:
            counts = owner.memory_module.merge_snapshot(message.content)
            accepted = sum(counts.values())
            rejected = 1 if accepted == 0 else 0
        elif message.performative == INFORM_CURRENT_TASK:
            task = message.content.get("task")
            if task:
                before = len(owner.memory_module.known_tasks)
                owner.memory_module.remember_task(task, message.tick)
                accepted = 1 if len(owner.memory_module.known_tasks) >= before else 0
            else:
                rejected = 1
        elif message.performative == INFORM_CURRENT_TARGET:
            sender_state = {
                "agent_id": message.sender_id,
                "position": message.content.get("position"),
                "state": message.content.get("mode"),
                "current_task_id": message.content.get("current_task_id"),
                "current_target": message.content.get("current_target"),
            }
            owner.memory_module._set_newer(
                owner.memory_module.known_agents,
                message.sender_id,
                sender_state,
                message.tick,
            )
            accepted = 1
        else:
            rejected = 1

        self.knowledge_updates_received += accepted
        self.accepted_updates += accepted
        self.rejected_updates += rejected
        response_type = ACCEPT_UPDATE if accepted else REJECT_UPDATE
        result = {
            "performative": response_type,
            "sender_id": owner.agent_id,
            "receiver_id": message.sender_id,
            "accepted": accepted,
            "rejected": rejected,
            "source_performative": message.performative,
        }
        self.last_messages.append({**message.serialize(), "response": result})
        self.last_messages = self.last_messages[-20:]
        owner.agent_log_module.record(
            tick=message.tick,
            event_type="COMMUNICATION_OCCURRED",
            message=f"{owner.agent_id} received {message.performative} from {message.sender_id}.",
            data=result,
        )
        return result

    def _outgoing_messages(
        self,
        owner: "Agent",
        other: "Agent",
        tick: int,
    ) -> List[AgentMessage]:
        messages = [
            AgentMessage(
                performative=INFORM_MAP_UPDATE,
                sender_id=owner.agent_id,
                receiver_id=other.agent_id,
                tick=tick,
                content=owner.memory_module.export_for_communication(),
            ),
            AgentMessage(
                performative=INFORM_CURRENT_TARGET,
                sender_id=owner.agent_id,
                receiver_id=other.agent_id,
                tick=tick,
                content={
                    "position": owner.position,
                    "mode": owner.mode,
                    "current_task_id": owner.current_task_id,
                    "current_target": owner.current_target,
                },
            ),
        ]
        task = owner.current_task_snapshot()
        if task:
            messages.append(AgentMessage(
                performative=INFORM_CURRENT_TASK,
                sender_id=owner.agent_id,
                receiver_id=other.agent_id,
                tick=tick,
                content={"task": task},
            ))

        self.messages_sent += len(messages)
        self.last_messages.extend(message.serialize() for message in messages)
        self.last_messages = self.last_messages[-20:]
        return messages

    def serialize(self) -> Dict[str, object]:
        return {
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "knowledge_updates_received": self.knowledge_updates_received,
            "accepted_updates": self.accepted_updates,
            "rejected_updates": self.rejected_updates,
            "last_messages": self.last_messages[-5:],
        }
