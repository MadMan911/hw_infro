import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from src.agents.registry import AgentCard
from src.agents.tools.common import ESCALATE_TOOL

logger = logging.getLogger(__name__)


class AgentRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    metadata: dict = Field(default_factory=dict)


class AgentResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    content: str
    agent_id: str
    model_used: str = ""
    escalation: dict | None = None  # {"reason": ..., "target": ...} if escalated
    metadata: dict = Field(default_factory=dict)


@dataclass
class EscalationSignal:
    reason: str
    target: str


@dataclass
class ReActResult:
    content: str
    escalation: EscalationSignal | None = None
    model_used: str = ""
    steps: int = 0


class BaseAgent(ABC):
    """Abstract base class for all agents with ReAct loop."""

    def __init__(self, card: AgentCard, model: str, max_steps: int = 6) -> None:
        self.card = card
        self.model = model
        self.max_steps = max_steps

    def get_card(self) -> AgentCard:
        return self.card

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this agent."""

    @abstractmethod
    def get_tools(self) -> list[dict]:
        """Return tool definitions (OpenAI format) for this agent."""

    @abstractmethod
    def get_tool_executors(self) -> dict:
        """Return mapping of tool_name -> callable."""

    def _all_tools(self) -> list[dict]:
        """Agent tools + escalate tool."""
        return self.get_tools() + [ESCALATE_TOOL]

    def _all_executors(self) -> dict:
        """Agent executors + escalate executor."""
        executors = self.get_tool_executors().copy()
        executors["escalate"] = lambda **kwargs: kwargs  # returns args as-is
        return executors

    async def react_loop(self, user_message: str, context: str = "") -> ReActResult:
        """Run the ReAct loop: LLM decides which tools to call, max_steps iterations."""
        import litellm

        messages = [{"role": "system", "content": self.get_system_prompt()}]
        if context:
            messages.append({"role": "system", "content": f"Контекст от предыдущего агента: {context}"})
        messages.append({"role": "user", "content": user_message})

        tools = self._all_tools()
        executors = self._all_executors()

        for step in range(self.max_steps):
            response = await litellm.acompletion(
                model=self.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )

            choice = response.choices[0]
            message = choice.message

            # No tool calls — final answer
            if not message.tool_calls:
                return ReActResult(
                    content=message.content or "",
                    model_used=self.model,
                    steps=step + 1,
                )

            # Append assistant message with tool calls
            messages.append(message.model_dump())

            # Execute each tool call
            for tool_call in message.tool_calls:
                fn_name = tool_call.function.name
                fn_args = json.loads(tool_call.function.arguments)

                logger.info("Agent %s step %d: calling %s(%s)", self.card.id, step + 1, fn_name, fn_args)

                # Check for escalation
                if fn_name == "escalate":
                    return ReActResult(
                        content=message.content or "",
                        escalation=EscalationSignal(
                            reason=fn_args["reason"],
                            target=fn_args["target"],
                        ),
                        model_used=self.model,
                        steps=step + 1,
                    )

                # Execute tool
                executor = executors.get(fn_name)
                if executor:
                    result = executor(**fn_args)
                else:
                    result = f"Unknown tool: {fn_name}"

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                })

        # Max steps reached — return whatever we have
        last_response = await litellm.acompletion(
            model=self.model,
            messages=messages,
        )
        return ReActResult(
            content=last_response.choices[0].message.content or "Превышен лимит шагов обработки.",
            model_used=self.model,
            steps=self.max_steps,
        )

    async def handle(self, request: AgentRequest) -> AgentResponse:
        """Process a user request using the ReAct loop."""
        import time
        start = time.monotonic()
        context = request.metadata.get("escalation_reason", "")
        result = await self.react_loop(request.message, context=context)
        latency = time.monotonic() - start

        escalation = None
        if result.escalation:
            escalation = {
                "reason": result.escalation.reason,
                "target": result.escalation.target,
            }

        # MLFlow tracing (non-fatal)
        try:
            from src.telemetry.mlflow_tracer import AgentCallMetrics, get_tracer
            metrics = AgentCallMetrics(
                agent_id=self.card.id,
                model=result.model_used,
                latency=latency,
                steps=result.steps,
                escalated=result.escalation is not None,
            )
            await get_tracer().trace_agent_call(
                request_message=request.message,
                response_content=result.content,
                metrics=metrics,
            )
        except Exception:
            pass

        return AgentResponse(
            content=result.content,
            agent_id=self.card.id,
            model_used=result.model_used,
            escalation=escalation,
            metadata={"steps": result.steps},
        )
