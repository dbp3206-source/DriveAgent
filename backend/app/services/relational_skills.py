"""Portable Skills persistence for the cloud profile.

The caller owns the engine and its credentials. This adapter neither reads a
host API key nor copies local Skills into the cloud. PostgreSQL and SQLite use
the same optimistic revision contract; concurrent writers cannot silently win.
"""

import time
from uuid import uuid4

from sqlalchemy import (
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.services.relational_state import close_state_engines as close_state_engines
from app.services.relational_state import state_engine
from app.services.skills import SkillSpec, SkillStore
from app.tools.contracts import ToolError

metadata = MetaData()
skills = Table(
    "skills",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("spec", Text, nullable=False),
    Column("revision", Integer, nullable=False),
    Column("active", Integer, nullable=False),
    Column("created", Float, nullable=False),
    Column("updated", Float, nullable=False),
    UniqueConstraint("user_id", "name", name="uq_skills_user_name"),
)


def skill_store(settings: Settings) -> SkillStore:
    if settings.relational_state_url is None:
        return SkillStore(settings.data_dir)
    return RelationalSkillStore(state_engine(settings.relational_state_url.get_secret_value()))


def initialize_skill_store(settings: Settings) -> None:
    if settings.relational_state_url is not None:
        RelationalSkillStore.create_schema(
            state_engine(settings.relational_state_url.get_secret_value())
        )


class RelationalSkillStore(SkillStore):
    """Reuse validation/expansion, not SQLite connections or filesystem state."""

    def __init__(self, engine: Engine):
        if engine.dialect.name not in {"sqlite", "postgresql"}:
            raise ValueError("Skills persistence requires SQLite or PostgreSQL")
        self.engine = engine

    @staticmethod
    def create_schema(engine: Engine) -> None:
        """Explicit migration/bootstrap step; normal requests never create DDL."""
        metadata.create_all(engine)

    def save(self, user_id: str, spec: SkillSpec, expected_revision: int | None = None) -> dict:
        now = time.time()
        skill_id = str(uuid4())
        try:
            with self.engine.begin() as db:
                old = db.execute(
                    select(skills.c.id, skills.c.revision).where(
                        skills.c.user_id == user_id, skills.c.name == spec.name
                    )
                ).mappings().first()
                if old:
                    if expected_revision is None or old["revision"] != expected_revision:
                        raise ToolError("Skill đã thay đổi; tải lại trước khi lưu.",
                                        code="revision_conflict")
                    skill_id = old["id"]
                    changed = db.execute(
                        update(skills).where(
                            skills.c.id == skill_id,
                            skills.c.user_id == user_id,
                            skills.c.revision == expected_revision,
                        ).values(spec=spec.model_dump_json(), revision=expected_revision + 1,
                                 active=1, updated=now)
                    ).rowcount
                    if changed != 1:
                        raise ToolError("Skill đã thay đổi; tải lại trước khi lưu.",
                                        code="revision_conflict")
                else:
                    if expected_revision not in {None, 0}:
                        raise ToolError("Không tìm thấy phiên bản skill.", code="skill_not_found")
                    db.execute(insert(skills).values(
                        id=skill_id, user_id=user_id, name=spec.name,
                        spec=spec.model_dump_json(), revision=1, active=1,
                        created=now, updated=now,
                    ))
        except IntegrityError as exc:
            # Two simultaneous creates of the same owner/name: no overwrite.
            raise ToolError("Skill đã thay đổi; tải lại trước khi lưu.",
                            code="revision_conflict") from exc
        return self.get(user_id, skill_id)

    def list(self, user_id: str, include_archived: bool = False) -> list[dict]:
        query = select(skills).where(skills.c.user_id == user_id)
        if not include_archived:
            query = query.where(skills.c.active == 1)
        with self.engine.connect() as db:
            rows = db.execute(query.order_by(skills.c.updated.desc())).mappings().all()
        return [self._decode(row) for row in rows]

    def get(self, user_id: str, skill_id_or_name: str) -> dict:
        with self.engine.connect() as db:
            row = db.execute(select(skills).where(
                skills.c.user_id == user_id,
                (skills.c.id == skill_id_or_name) | (skills.c.name == skill_id_or_name),
            )).mappings().first()
        if row is None:
            raise ToolError("Không tìm thấy skill.", code="skill_not_found")
        return self._decode(row)

    def archive(self, user_id: str, skill_id: str) -> dict:
        with self.engine.begin() as db:
            changed = db.execute(update(skills).where(
                skills.c.id == skill_id, skills.c.user_id == user_id,
            ).values(active=0, updated=time.time())).rowcount
            if changed != 1:
                raise ToolError("Không tìm thấy skill.", code="skill_not_found")
        return self.get(user_id, skill_id)
