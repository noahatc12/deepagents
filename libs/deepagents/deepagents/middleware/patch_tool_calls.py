"""Middleware to patch dangling tool calls in the messages history."""

from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Overwrite


class PatchToolCallsMiddleware(AgentMiddleware):
    """Middleware to patch dangling tool calls in the messages history.

    When a tool call is made but no corresponding ToolMessage exists (e.g., due
    to user interruption, context overflow, or an error), this middleware injects
    a synthetic ToolMessage so the conversation history remains well-formed for
    the model.
    """

    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:  # noqa: ARG002
        """Before the agent runs, handle dangling tool calls from any AIMessage."""
        messages = state["messages"]
        if not messages or len(messages) == 0:
            return None

        patched_messages = []
        has_patches = False
        # Iterate over the messages and add any dangling tool calls
        for i, msg in enumerate(messages):
            patched_messages.append(msg)
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    corresponding_tool_msg = next(
                        (msg for msg in messages[i:] if msg.type == "tool" and msg.tool_call_id == tool_call["id"]),  # ty: ignore[unresolved-attribute]
                        None,
                    )
                    if corresponding_tool_msg is None:
                        has_patches = True
                        # Determine context for why the tool call is dangling
                        is_last_message = i == len(messages) - 1
                        has_following_human = any(
                            isinstance(m, HumanMessage) for m in messages[i + 1:]
                        )

                        if is_last_message:
                            reason = "was interrupted before it could be executed"
                        elif has_following_human:
                            reason = "was not executed — the user sent a new message before it completed"
                        else:
                            reason = "was cancelled before it could be completed"

                        tool_msg = (
                            f"Tool call `{tool_call['name']}` (id: {tool_call['id']}) {reason}. "
                            f"The tool was NOT executed and produced no result. "
                            f"If this tool call is still needed, you should re-invoke it."
                        )
                        patched_messages.append(
                            ToolMessage(
                                content=tool_msg,
                                name=tool_call["name"],
                                tool_call_id=tool_call["id"],
                            )
                        )

        if not has_patches:
            return None

        return {"messages": Overwrite(patched_messages)}
