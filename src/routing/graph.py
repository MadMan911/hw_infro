"""LangGraph multi-agent orchestration graph."""

import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.agents.base import AgentRequest, BaseAgent
from src.agents.registry import AgentRegistry
from src.routing.classifier import RequestClassifier

logger = logging.getLogger(__name__)

MAX_ESCALATIONS = 3


class AgentState(TypedDict):
    user_message: str
    current_agent: str
    visited_agents: list[str]
    escalation_reason: str
    final_response: str
    agent_trace: list[dict]  # [{agent_id, action, content}, ...]


def _make_agent_node(agent: BaseAgent):
    """Create a graph node function for a given agent."""

    async def node(state: AgentState) -> dict:
        request = AgentRequest(
            message=state["user_message"],
            metadata={"escalation_reason": state.get("escalation_reason", "")},
        )

        response = await agent.handle(request)

        visited = state["visited_agents"] + [agent.card.id]
        trace_entry = {
            "agent_id": agent.card.id,
            "model_used": response.model_used,
            "steps": response.metadata.get("steps", 0),
        }
        trace = state.get("agent_trace", []) + [trace_entry]

        if response.escalation:
            target = response.escalation["target"]
            reason = response.escalation["reason"]

            logger.info(
                "Agent %s escalating to %s: %s",
                agent.card.id, target, reason,
            )

            # Check escalation depth
            if len(visited) >= MAX_ESCALATIONS:
                target = "escalation"
                reason = f"Превышен лимит эскалаций. Последняя причина: {reason}"

            return {
                "current_agent": target,
                "visited_agents": visited,
                "escalation_reason": reason,
                "final_response": "",
                "agent_trace": trace,
            }

        return {
            "current_agent": "",
            "visited_agents": visited,
            "final_response": response.content,
            "escalation_reason": "",
            "agent_trace": trace,
        }

    return node


async def classify_node(state: AgentState) -> dict:
    """Classification node — determines which agent to route to."""
    classifier: RequestClassifier = classify_node._classifier  # type: ignore[attr-defined]

    result = await classifier.classify(state["user_message"])
    logger.info(
        "Classified: method=%s, topic=%s, confidence=%.2f",
        result.method, result.topic, result.confidence,
    )

    # Map method to agent type
    method_to_agent = {
        "faq": "faq",
        "general_question": "faq",
        "diagnostics": "diagnostics",
        "billing": "billing",
        "escalation": "escalation",
    }
    agent_key = method_to_agent.get(result.method, "faq")

    return {
        "current_agent": agent_key,
        "agent_trace": [{"agent_id": "classifier", "method": result.method, "topic": result.topic, "confidence": result.confidence}],
    }


def route_after_agent(state: AgentState) -> str:
    """Decide where to go after an agent runs."""
    if state.get("final_response"):
        return "done"

    target = state.get("current_agent", "")
    visited = state.get("visited_agents", [])

    # Map target method to node name
    target_map = {
        "faq": "faq_agent",
        "diagnostics": "diagnostics_agent",
        "billing": "billing_agent",
        "escalation": "human_router",
    }

    node_name = target_map.get(target, "human_router")

    # Prevent visiting the same agent twice
    agent_id_map = {
        "faq_agent": "faq-agent",
        "diagnostics_agent": "diagnostics-agent",
        "billing_agent": "billing-agent",
        "human_router": "human-router-agent",
    }

    if agent_id_map.get(node_name) in visited:
        return "human_router"

    return node_name


def route_after_classify(state: AgentState) -> str:
    """Route from classifier to the appropriate agent node."""
    return route_after_agent(state)


def build_graph(
    agents: dict[str, BaseAgent],
    classifier: RequestClassifier,
) -> StateGraph:
    """Build the multi-agent LangGraph.

    Args:
        agents: mapping of agent key to agent instance
                 keys: "faq", "diagnostics", "billing", "human_router"
        classifier: the request classifier
    """
    classify_node._classifier = classifier  # type: ignore[attr-defined]

    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("classify", classify_node)
    graph.add_node("faq_agent", _make_agent_node(agents["faq"]))
    graph.add_node("diagnostics_agent", _make_agent_node(agents["diagnostics"]))
    graph.add_node("billing_agent", _make_agent_node(agents["billing"]))
    graph.add_node("human_router", _make_agent_node(agents["human_router"]))

    # Entry point
    graph.set_entry_point("classify")

    # Edges from classifier
    graph.add_conditional_edges("classify", route_after_classify, {
        "faq_agent": "faq_agent",
        "diagnostics_agent": "diagnostics_agent",
        "billing_agent": "billing_agent",
        "human_router": "human_router",
    })

    # Edges from each agent — either escalate to another or finish
    for node_name in ["faq_agent", "diagnostics_agent", "billing_agent"]:
        graph.add_conditional_edges(node_name, route_after_agent, {
            "faq_agent": "faq_agent",
            "diagnostics_agent": "diagnostics_agent",
            "billing_agent": "billing_agent",
            "human_router": "human_router",
            "done": END,
        })

    # Human router always ends
    graph.add_edge("human_router", END)

    return graph


async def run_graph(graph, user_message: str) -> dict:
    """Execute the compiled graph with a user message."""
    compiled = graph.compile()

    initial_state: AgentState = {
        "user_message": user_message,
        "current_agent": "",
        "visited_agents": [],
        "escalation_reason": "",
        "final_response": "",
        "agent_trace": [],
    }

    result = await compiled.ainvoke(initial_state)
    return result
