"""User-selected Chat Harness controls.

These values come from the slash menu. They are enforced before a model sees the
request, so choosing a source or specialist is a real execution boundary rather
than a suggestion hidden in prompt text.
"""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.evidence import context_only_followup

_COMMAND_PATCHES: dict[str, dict[str, str]] = {
    "/auto": {"source": "auto"},
    "/drive": {"source": "drive", "agent": "research"},
    "/rag": {"source": "rag", "agent": "research"},
    "/gmail": {"source": "gmail", "agent": "communication"},
    "/local": {"source": "local", "agent": "research"},
    "/memory": {"source": "memory", "agent": "study"},
    "/general": {"source": "general"},
    "/research": {"agent": "research", "output": "chat"},
    "/communication": {"agent": "communication", "source": "gmail", "output": "chat"},
    "/study": {"agent": "study", "output": "chat"},
    "/workspace": {"agent": "workspace"},
    "/summary": {"workflow": "source_summary"},
    "/inbox": {"workflow": "email_digest", "source": "gmail", "agent": "communication"},
    "/meeting": {"workflow": "meeting_notes"},
    "/study-plan": {"workflow": "study_plan", "agent": "study"},
    "/budget": {
        "workflow": "budget_tracker",
        "output": "spreadsheet",
        "agent": "workspace",
        "source": "general",
    },
    "/compare": {"workflow": "compare_sources", "agent": "research"},
    "/chat": {"output": "chat"},
    "/doc": {"output": "document", "agent": "workspace"},
    "/sheet": {"output": "spreadsheet", "agent": "workspace"},
}

SourceChoice = Literal["auto", "drive", "rag", "gmail", "local", "memory", "general"]
RestrictedSource = Literal["drive", "gmail", "local", "memory"]
AgentChoice = Literal["auto", "research", "communication", "study", "workspace"]
OutputChoice = Literal["chat", "document", "spreadsheet"]
WorkflowChoice = Literal[
    "auto",
    "source_summary",
    "email_digest",
    "meeting_notes",
    "study_plan",
    "budget_tracker",
    "compare_sources",
]


class ChatControls(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: SourceChoice = "auto"
    agent: AgentChoice = "auto"
    output: OutputChoice = "chat"
    workflow: WorkflowChoice = "auto"
    # Server-derived from explicit negative instructions. It is intentionally
    # restrictive: a source exclusion can only remove capabilities.
    excluded_sources: frozenset[RestrictedSource] = Field(default_factory=frozenset)
    skill_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=260,
        pattern=r"^[a-z0-9_]+(?:\+[a-z0-9_]+){0,3}$",
    )

    def selected_skill_names(self) -> tuple[str, ...]:
        """Return the ordered, de-duplicated saved-skill chain."""

        if not self.skill_name:
            return ()
        return tuple(dict.fromkeys(self.skill_name.split("+")))

    @model_validator(mode="after")
    def reject_conflicting_specialist(self) -> "ChatControls":
        # Workspace is the governed output/compiler role.  It may gather from a
        # selected source before preparing a Doc/Sheet, so it is intentionally
        # compatible with Drive, RAG, Gmail, local and Memory sources.
        if self.agent == "workspace" and self.output in {"document", "spreadsheet"}:
            return self
        expected = {
            "drive": "research",
            "rag": "research",
            "local": "research",
            "gmail": "communication",
            "memory": "study",
        }.get(self.source)
        if expected and self.agent not in {"auto", expected}:
            raise ValueError(
                f"Nguồn {self.source} không tương thích với agent {self.agent}."
            )
        # Workspace outputs use the governed compiler after gathering the chosen
        # source. The selected agent remains the content role, not a write path.
        return self

    def effective_agent(self) -> AgentChoice:
        if self.agent != "auto":
            return self.agent
        return {
            "drive": "research",
            "rag": "research",
            "local": "research",
            "gmail": "communication",
            "memory": "study",
        }.get(self.source, "auto")  # type: ignore[return-value]

    def align_with_route(self, route: object) -> tuple["ChatControls", dict[str, str] | None]:
        """Keep an explicit read route usable when the selected specialist differs.

        The composer agent is a response style/specialist, not a reason to silently
        discard a clearly named source. An explicit source choice still wins; only
        Auto is aligned to a deterministic route. Workspace keeps its role and gains
        the matching read source so it can perform a governed read-then-propose flow.
        """

        tool = getattr(route, "tool", None)
        if self.source != "auto" or not isinstance(tool, str):
            return self, None
        source_for_prefix = {
            "gmail_": "gmail",
            "drive_": "drive",
            "rag_": "rag",
            "local_source_": "local",
            "memory_": "memory",
        }
        inferred_source = next(
            (source for prefix, source in source_for_prefix.items() if tool.startswith(prefix)),
            None,
        )
        if not inferred_source or inferred_source in self.excluded_sources or (
            inferred_source == "rag" and "drive" in self.excluded_sources
        ):
            return self, None
        expected_agent = {
            "gmail": "communication",
            "drive": "research",
            "rag": "research",
            "local": "research",
            "memory": "study",
        }[inferred_source]
        changes: dict[str, str] = {}
        if self.agent == "workspace":
            changes["source"] = inferred_source
        elif self.agent != expected_agent:
            changes["agent"] = expected_agent
        if not changes:
            return self, None
        updated = self.model_copy(update=changes)
        return updated, {
            "from_agent": self.effective_agent(),
            "to_agent": updated.effective_agent(),
            "source": inferred_source,
            "reason": "explicit_source_route",
        }

    def parse_leading_commands(self, message: str) -> tuple["ChatControls", str]:
        """Apply typed slash commands and return the clean user request.

        Clicking the slash menu already sends typed controls. Keyboard-first users may
        instead type one or more exact commands before their request. Parse only that
        leading prefix: a slash appearing later in prose remains ordinary content.
        """

        tokens = message.strip().split()
        controls = self
        consumed = 0
        for token in tokens:
            normalized = token.casefold()
            patch = _COMMAND_PATCHES.get(normalized)
            if patch is None and normalized.startswith("/skill:"):
                skill_name = normalized.removeprefix("/skill:")
                if not skill_name or not skill_name.replace("_", "a").isalnum():
                    break
                existing = controls.selected_skill_names()
                if skill_name not in existing:
                    if len(existing) >= 4:
                        break
                    skill_name = "+".join((*existing, skill_name))
                else:
                    skill_name = "+".join(existing)
                patch = {"skill_name": skill_name}
            if patch is None:
                break
            controls = controls._merge_command_patch(patch)
            consumed += 1
        return controls, " ".join(tokens[consumed:])

    def _merge_command_patch(self, patch: dict[str, str]) -> "ChatControls":
        data = self.model_dump()
        data.update(patch)
        requested_source = patch.get("source")
        requested_agent = patch.get("agent")
        expected_by_source = {
            "drive": "research",
            "rag": "research",
            "local": "research",
            "gmail": "communication",
            "memory": "study",
        }
        if requested_source and requested_source != "auto":
            compatible = expected_by_source.get(requested_source)
            if compatible and data["agent"] not in {"auto", "workspace", compatible}:
                data["agent"] = compatible
            elif compatible and data["agent"] == "auto":
                data["agent"] = compatible
        if requested_agent and requested_agent not in {"auto", "workspace"}:
            compatible = expected_by_source.get(data["source"])
            if compatible and compatible != requested_agent:
                data["source"] = "auto"
        return ChatControls.model_validate(data)

    def enforce_explicit_message_source(self, message: str) -> "ChatControls":
        """Convert an explicit RAG-only request into a server-side tool boundary.

        The slash menu remains authoritative when the user selected a source.  If
        it is still on Auto, wording such as ``chỉ dùng RAG`` must not be treated
        as a soft model hint: a stale-index error may never fall back to Drive.
        """

        if self.source != "auto":
            return self
        normalized = message.casefold()
        if "rag_search" in normalized or "chỉ dùng rag" in normalized or (
            "lập chỉ mục" in normalized and "chỉ" in normalized
        ):
            return self.model_copy(update={"source": "rag"})
        # Named files alone can live in Drive. Infer local only when the user
        # explicitly restricts reading to named files and excludes Drive.
        exclusions = self.enforce_explicit_source_exclusions(message).excluded_sources
        if (
            "drive" in exclusions and "local" not in exclusions
            and re.search(
                r"(?<!không )(?<!đừng )\bchỉ\s+(?:đọc|dùng|sử\s+dụng)\b", normalized
            )
            and re.search(r"[\w.-]+\.(?:md|txt|csv|ipynb|pdf|docx|xlsx)\b", normalized)
        ):
            return self.model_copy(update={"source": "local"})
        if re.search(
            r"(?<!không )(?<!đừng )\bchỉ\s+(?:dùng|sử\s+dụng)\b"
            r"[^.!?\n]{0,120}\b(?:tài\s+liệu|tệp)\s+local\b",
            normalized,
        ):
            return self.model_copy(update={"source": "local"})
        return self

    def enforce_explicit_source_exclusions(self, message: str) -> "ChatControls":
        """Turn clear natural-language source prohibitions into tool denials.

        The router is intentionally keyword-driven. Without this policy layer,
        a sentence such as "do not access Gmail/Drive" can look like a Gmail
        request merely because it names Gmail. Exclusions therefore run before
        route selection and remain in force even if a route override exists.
        """

        exclusions = set(self.excluded_sources)
        # A context-only follow-up must not acquire new private evidence merely
        # because the request mentions memory in a prohibition on saving it.
        if context_only_followup(message):
            exclusions.update({"drive", "gmail", "local", "memory"})
        clauses = re.split(r"[.!?;\n]+", message.casefold())
        negative_action = re.compile(
            r"(?:\b(?:không|khong|đừng|dung|no)\s+"
            r"(?:(?:trực\s+tiếp|truy\s+cập|truy\s+cap|dùng|dung|đọc|doc|"
            r"tra\s+cứu|tra\s+cuu|tìm\s+kiếm|tim\s+kiem|lấy|lay|"
            r"access|use|read|search|query|fetch|look\s+up)\s+){1,4}"
            r"|\b(?:không|khong|đừng|no)\s+"
            r"(?=(?:gmail|e-?mail|mail|hộp\s+thư|google\s+drive|drive|"
            r"tài\s+liệu\s+local|local\s+files?|bộ\s+nhớ|memory)\b)"
            r"|\b(?:do\s+not|don't|dont|without)\s+"
            r"(?:(?:directly|access|accessing|use|using|read|reading|search|"
            r"query|fetch|looking\s+up)\s+){1,4})",
            re.IGNORECASE,
        )
        source_patterns: dict[str, re.Pattern[str]] = {
            "gmail": re.compile(r"\b(?:gmail|e-?mail|mail|hộp\s+thư)\b", re.I),
            "drive": re.compile(r"\b(?:google\s+drive|drive)\b", re.I),
            "local": re.compile(r"\b(?:tài\s+liệu\s+local|local\s+files?)\b", re.I),
            "memory": re.compile(r"\b(?:bộ\s+nhớ|memory)\b", re.I),
        }
        for clause in clauses:
            # A contrast or an explicit positive action starts a new scope:
            # "don't use Gmail, but do use Drive" must block only Gmail.
            scoped_clauses = re.split(
                r"\b(?:nhưng|mà|trái\s+lại|but|however|instead)\b|"
                r"(?:\b(?:and|và)\s+(?:use|access|read|search|query|fetch|"
                r"dùng|truy\s+cập|đọc|tra\s+cứu|tìm\s+kiếm)\b)",
                clause,
                flags=re.I,
            )
            for scoped_clause in scoped_clauses:
                prohibition = negative_action.search(scoped_clause)
                if prohibition is None:
                    continue
                prohibited_scope = scoped_clause[prohibition.end():]
                exclusions.update(
                    source
                    for source, pattern in source_patterns.items()
                    if pattern.search(prohibited_scope)
                )
        if exclusions == set(self.excluded_sources):
            return self
        return self.model_copy(update={"excluded_sources": frozenset(exclusions)})

    def filter_excluded_route(self, route: object) -> object:
        """Remove routes that would violate an explicit source exclusion."""

        tool = getattr(route, "tool", None)
        sources = getattr(route, "sources", ())
        prefixes_by_source = {
            "gmail": ("gmail_",),
            # RAG is an index of Drive content in this product, so a Drive
            # exclusion also excludes indexed Drive retrieval.
            "drive": ("drive_", "rag_"),
            "local": ("local_source_",),
            "memory": ("memory_",),
        }

        def is_excluded(tool_name: str | None) -> bool:
            return bool(
                tool_name
                and any(
                    tool_name.startswith(prefix)
                    for source in self.excluded_sources
                    for prefix in prefixes_by_source[source]
                )
            )

        if is_excluded(tool):
            from app.agent.routing import Route

            return Route()
        if sources:
            if any(is_excluded(getattr(source, "tool", None)) for source in sources):
                # A partial multi-source comparison could mislead; do not
                # silently answer from only the unblocked half.
                from app.agent.routing import Route

                return Route(
                    direct=True,
                    clarification=(
                        "Yêu cầu có nhắc tới nguồn bạn đã cấm truy cập. Tôi đã không đọc nguồn đó; "
                        "hãy gửi nội dung cần đối chiếu trực tiếp hoặc cho phép nguồn phù hợp."
                    ),
                )
        return route

    def allowed_tool_names(
        self,
        available: list[str],
        skill_capabilities: frozenset[str] | set[str] | None = None,
    ) -> set[str]:
        """Return the concrete allow-list after source and specialist selection."""

        prefixes_by_source = {
            "drive": ("drive_",),
            "rag": ("rag_",),
            "gmail": ("gmail_",),
            "local": ("local_source_",),
            "memory": ("memory_",),
            "general": (),
        }
        prefixes_by_agent = {
            "research": ("drive_", "rag_", "local_source_", "web_research"),
            "communication": ("gmail_",),
            "study": ("memory_", "artifact_"),
            "workspace": ("docs_", "sheets_", "skill_"),
        }
        names = set(available)
        effective_agent = self.effective_agent()
        if self.skill_name and self.source == "auto":
            # A saved skill is a reusable workflow with an explicit capability
            # contract. Do not let whichever specialist happened to be selected
            # hide those tools, and fail closed if the server did not resolve its
            # saved capabilities.
            names = {"skill_run"}
            prefixes = {
                "drive": ("drive_",),
                "rag": ("rag_",),
                "memory": ("memory_",),
                "docs": ("docs_",),
                "sheets": ("sheets_",),
                "gmail": ("gmail_",),
                "artifacts": ("artifact_",),
            }
            for capability in skill_capabilities or ():
                names.update(
                    name for name in available
                    if any(name.startswith(prefix) for prefix in prefixes.get(capability, ()))
                )
        elif self.source != "auto":
            prefixes = prefixes_by_source[self.source]
            names = {name for name in names if any(name.startswith(p) for p in prefixes)}
        if effective_agent != "auto" and not self.skill_name:
            prefixes = prefixes_by_agent[effective_agent]
            # A workspace output still needs the selected read source.  Keep
            # writer tools as well as source tools; the compiler decides the
            # actual read-then-propose sequence.
            if effective_agent == "workspace" and self.source != "auto":
                source_prefixes = prefixes_by_source[self.source]
                prefixes = (*prefixes, *source_prefixes)
            names = {name for name in names if any(name.startswith(p) for p in prefixes)}
            if effective_agent == "study" and "calculate" in available:
                names.add("calculate")
        if self.skill_name:
            names.update(name for name in available if name == "skill_run")
        excluded_prefixes = {
            "gmail": ("gmail_",),
            "drive": ("drive_", "rag_"),
            "local": ("local_source_",),
            "memory": ("memory_",),
        }
        names = {
            name
            for name in names
            if not any(
                name.startswith(prefix)
                for source in self.excluded_sources
                for prefix in excluded_prefixes[source]
            )
        }
        return names

    def instruction(self) -> str:
        workflow_labels = {
            "source_summary": "tóm tắt có dẫn chứng từ nguồn đã chọn",
            "email_digest": (
                "lập bản tổng hợp email theo mức ưu tiên và hành động tiếp theo; "
                "phân biệt deadline với giờ diễn ra sự kiện, không đổi giờ sự kiện thành deadline; "
                "không suy ra email cần trả lời nếu nội dung không yêu cầu"
            ),
            "meeting_notes": (
                "trình bày biên bản gồm quyết định, việc cần làm, người phụ trách và hạn"
            ),
            "study_plan": "lập lộ trình học có mục tiêu, bước thực hành và cách tự kiểm tra",
            "budget_tracker": "lập bảng theo dõi ngân sách có công thức kiểm tra",
            "compare_sources": "so sánh các nguồn theo tiêu chí nhất quán và nêu khác biệt",
        }
        parts = [
            f"Nguồn do người dùng chọn: {self.source}.",
            f"Agent do người dùng chọn: {self.effective_agent()}.",
            f"Đầu ra do người dùng chọn: {self.output}.",
        ]
        if self.excluded_sources:
            excluded = ", ".join(sorted(self.excluded_sources))
            parts.append(
                f"Nguồn bị cấm trong yêu cầu này: {excluded}. Không đọc, gọi công cụ, "
                "hoặc tái sử dụng dữ liệu/citation từ các nguồn đó; chỉ dùng nội dung "
                "người dùng cung cấp trực tiếp trong lượt hiện tại."
            )
        if self.workflow != "auto":
            parts.append(f"Quy trình cần theo: {workflow_labels[self.workflow]}.")
        if self.skill_name:
            names = self.selected_skill_names()
            if len(names) == 1:
                parts.append(f"Chạy đúng skill có tên kỹ thuật: {names[0]}.")
            else:
                parts.append(
                    "Phối hợp chuỗi skill đã lưu theo đúng thứ tự: "
                    + " → ".join(names)
                    + ". Hoàn tất đầu ra của skill trước làm đầu vào có cấu trúc cho skill sau; "
                    "không bỏ qua ràng buộc hoặc tự mở rộng quyền công cụ."
                )
        return " ".join(parts)
