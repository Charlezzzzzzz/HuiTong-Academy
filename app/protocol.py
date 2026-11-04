from __future__ import annotations

from .model_gateway import ModelGateway
from .memory_bridge import MemoryBridge
from .schemas import ResearchRequest
from .storage import SQLiteStore


class Protocol:
    def __init__(self, store=None, gateway=None, memory=None):
        self.store = store or SQLiteStore()
        self.gateway = gateway or ModelGateway()
        self.memory = memory or MemoryBridge()

    def create_room(self, topic="", mode="learning", task_id="daofu"):
        room = self.store.create_room(topic, mode=mode, task_id=task_id)
        self.store.add_event(room.id, "room.created", {"mode": mode, "task_id": task_id})
        return room.to_dict()

    def room_state(self, room_id):
        return self.store.room_state(room_id)

    def join_room(self, room_id, seat_id, display_name="学习者", kind="human"):
        participant = self.store.join_room(room_id, seat_id, display_name, kind)
        self.store.add_event(room_id, "participant.joined", participant.to_dict(), actor_id=participant.id)
        return participant.to_dict()

    def add_event(self, room_id, type, payload=None, **kwargs):
        return self.store.add_event(room_id, type, payload, **kwargs).to_dict()

    def room_events(self, room_id, after_seq=0):
        return [event.to_dict() for event in self.store.list_events(room_id, after_seq)]

    def retrieve_context(self, room_id, query, limit=8, hops=1):
        """Retrieve room context through the local GraphRAG node/edge index."""
        self.store.room_state(room_id)
        graph = getattr(self.store, "graph", None)
        if graph is None:
            return {
                "query": query,
                "context_text": "",
                "nodes": [],
                "edges": [],
                "retrieval": {"method": "unavailable", "room_id": room_id, "seed_count": 0, "node_count": 0, "edge_count": 0, "hops": 0},
            }
        return graph.retrieve(query, room_id=room_id, limit=limit, hops=hops)

    def research(self, room_id, question, context="", agent_id=None):
        request = ResearchRequest(room_id, question, context).validate()
        retrieval = self.retrieve_context(room_id, request.question)
        memory_retrieval = self.memory.context(request.question, agent_id=agent_id)
        context_blocks = []
        if request.context:
            context_blocks.append("用户提供的上下文：\n" + request.context)
        if retrieval.get("context_text"):
            context_blocks.append(
                "GraphRAG 检索到的房间节点与关系（只作为可核查上下文，不自动视为新事实）：\n"
                + retrieval["context_text"]
            )
        if memory_retrieval.get("context_text"):
            context_blocks.append(
                "跨项目长期记忆（按项目与智能体权限过滤，只作为可核查上下文）：\n"
                + memory_retrieval["context_text"]
            )
        messages = [
            {
                "role": "system",
                "content": "你是会通书院协议的研究助手。只输出 JSON object；区分事实、推测和待核验问题。GraphRAG 上下文只是检索结果，不能替代材料出处。",
            },
            {"role": "user", "content": request.question + ("\n\n" + "\n\n".join(context_blocks) if context_blocks else "")},
        ]
        result = self.gateway.complete(messages, response_format={"type": "json_object"})
        self.store.add_event(room_id, "research.completed", {
            "result": result,
            "retrieval": retrieval.get("retrieval", {}),
            "memory_retrieval": {
                "source": memory_retrieval.get("source"),
                "agent_id": memory_retrieval.get("agent_id"),
                "node_count": len(memory_retrieval.get("nodes", [])),
                "truncated": bool(memory_retrieval.get("truncated")),
            },
        })
        return result
