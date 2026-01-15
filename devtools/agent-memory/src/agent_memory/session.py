"""Session context management for agent-memory.

Provides functionality to capture, save, and retrieve session context
for session recovery across work sessions.

Implementation: T047 (FLO-632)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from agent_memory.cognee_client import CogneeClient


class DecisionRecord(BaseModel):
    """Record of a decision made during a session.

    Attributes:
        decision: What was decided.
        rationale: Why this decision was made.
        alternatives_considered: Other options evaluated.
        timestamp: When decision was made.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: str = Field(..., min_length=1, description="What was decided")
    rationale: str = Field(default="", description="Why this decision was made")
    alternatives_considered: list[str] = Field(
        default_factory=list, description="Other options evaluated"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When decision was made",
    )


class SessionContext(BaseModel):
    """Captured context for session recovery.

    Attributes:
        session_id: Unique session identifier.
        captured_at: When context was captured.
        active_work_areas: Files/areas being worked on.
        recent_decisions: Recent architectural decisions.
        related_closed_tasks: Related completed work.
        conversation_summary: Summary of session conversation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    session_id: UUID = Field(default_factory=uuid4, description="Unique session identifier")
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When context was captured",
    )
    active_work_areas: list[str] = Field(
        default_factory=list, description="Files/areas being worked on"
    )
    recent_decisions: list[DecisionRecord] = Field(
        default_factory=list, description="Recent architectural decisions"
    )
    related_closed_tasks: list[str] = Field(
        default_factory=list, description="Related completed work"
    )
    conversation_summary: str | None = Field(
        default=None, description="Summary of session conversation"
    )


def capture_session_context(
    active_issues: list[str],
    decisions: list[str],
    *,
    work_areas: list[str] | None = None,
    summary: str | None = None,
) -> SessionContext:
    """Capture session context from active issues and decisions.

    Creates a SessionContext model from the provided session information.

    Args:
        active_issues: List of issue IDs being worked on (e.g., ["FLO-123", "FLO-456"]).
        decisions: List of decision descriptions made during the session.
        work_areas: Optional list of work areas/files being touched.
        summary: Optional summary of the session conversation.

    Returns:
        SessionContext with the captured information.

    Example:
        >>> context = capture_session_context(
        ...     active_issues=["FLO-123", "FLO-456"],
        ...     decisions=["Use Pydantic v2 for all models"],
        ...     work_areas=["src/agent_memory/session.py"],
        ... )
        >>> context.related_closed_tasks
        ['FLO-123', 'FLO-456']
    """
    # Convert decision strings to DecisionRecord objects
    decision_records = [
        DecisionRecord(decision=d, timestamp=datetime.now(timezone.utc)) for d in decisions
    ]

    return SessionContext(
        active_work_areas=work_areas or [],
        recent_decisions=decision_records,
        related_closed_tasks=active_issues,
        conversation_summary=summary,
    )


async def save_session_context(
    client: CogneeClient,
    context: SessionContext,
    *,
    dataset: str = "sessions",
) -> None:
    """Save session context to the knowledge graph.

    Stores the session context in Cognee for later retrieval.

    Args:
        client: Cognee client for API operations.
        context: SessionContext to save.
        dataset: Dataset name to store context in (default: "sessions").

    Raises:
        CogneeClientError: If save operation fails.

    Example:
        >>> client = CogneeClient(config)
        >>> context = capture_session_context(...)
        >>> await save_session_context(client, context)
    """
    # Serialize context to a format suitable for storage
    content = _format_context_for_storage(context)

    # Add to Cognee as text content
    await client.add_content(
        content=content,
        dataset_name=dataset,
    )


async def retrieve_session_context(
    client: CogneeClient,
    work_area: str,
    *,
    dataset: str = "sessions",
    search_type: str = "GRAPH_COMPLETION",
) -> SessionContext | None:
    """Retrieve session context related to a work area.

    Searches the knowledge graph for prior session context
    matching the given work area.

    Args:
        client: Cognee client for API operations.
        work_area: Topic/area to recover context for.
        dataset: Dataset to search in (default: "sessions").
        search_type: Type of search to use (default: GRAPH_COMPLETION).

    Returns:
        SessionContext if found, None otherwise.

    Example:
        >>> client = CogneeClient(config)
        >>> context = await retrieve_session_context(client, "plugin-system")
        >>> if context:
        ...     print(f"Found prior work: {context.related_closed_tasks}")
    """
    # Search for relevant session context (scoped to sessions dataset)
    query = f"session context for {work_area}"
    search_result = await client.search(
        query, dataset_name=dataset, search_type=search_type
    )

    if not search_result.results:
        return None

    # Try to parse the most relevant result as SessionContext
    for result in search_result.results:
        context = _parse_context_from_result(result.content)
        if context is not None:
            return context

    return None


def _format_context_for_storage(context: SessionContext) -> str:
    """Format session context as text for storage.

    Args:
        context: SessionContext to format.

    Returns:
        Formatted text representation.
    """
    lines = [
        f"SESSION CONTEXT: {context.session_id}",
        f"Captured: {context.captured_at.isoformat()}",
        "",
    ]

    if context.active_work_areas:
        lines.append("Work Areas:")
        for area in context.active_work_areas:
            lines.append(f"  - {area}")
        lines.append("")

    if context.related_closed_tasks:
        lines.append("Related Tasks:")
        for task in context.related_closed_tasks:
            lines.append(f"  - {task}")
        lines.append("")

    if context.recent_decisions:
        lines.append("Decisions:")
        for decision in context.recent_decisions:
            lines.append(f"  - {decision.decision}")
            if decision.rationale:
                lines.append(f"    Rationale: {decision.rationale}")
        lines.append("")

    if context.conversation_summary:
        lines.append("Summary:")
        lines.append(f"  {context.conversation_summary}")

    return "\n".join(lines)


def _parse_context_from_result(content: str) -> SessionContext | None:
    """Parse session context from search result content.

    Attempts to extract session context information from
    a search result's content string.

    Args:
        content: Search result content to parse.

    Returns:
        SessionContext if successfully parsed, None otherwise.
    """
    # Look for session context markers
    if "SESSION CONTEXT:" not in content:
        return None

    try:
        # Parse basic structure
        work_areas: list[str] = []
        tasks: list[str] = []
        decisions: list[DecisionRecord] = []
        summary: str | None = None

        lines = content.split("\n")
        current_section: str | None = None

        for line in lines:
            line = line.strip()

            if line.startswith("Work Areas:"):
                current_section = "work_areas"
            elif line.startswith("Related Tasks:"):
                current_section = "tasks"
            elif line.startswith("Decisions:"):
                current_section = "decisions"
            elif line.startswith("Summary:"):
                current_section = "summary"
            elif line.startswith("- ") and current_section:
                value = line[2:].strip()
                if current_section == "work_areas":
                    work_areas.append(value)
                elif current_section == "tasks":
                    tasks.append(value)
                elif current_section == "decisions":
                    decisions.append(
                        DecisionRecord(decision=value, timestamp=datetime.now(timezone.utc))
                    )
            elif current_section == "summary" and line:
                summary = line

        return SessionContext(
            active_work_areas=work_areas,
            related_closed_tasks=tasks,
            recent_decisions=decisions,
            conversation_summary=summary,
        )

    except Exception:
        return None
