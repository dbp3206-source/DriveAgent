import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Base, User
from app.tools.contracts import ToolAccessDeniedError, ToolContext
from app.tools.documents import DRIVE_FILE_SCOPE, document_tool_definitions
from app.tools.registry import ToolRegistry
from app.tools.sheets import spreadsheet_tool_definitions


@pytest.mark.parametrize(
    "role,scopes,source,allowed",
    [
        ("owner", [DRIVE_FILE_SCOPE], "api", True),
        ("owner", [], "api", False),
        ("viewer", [DRIVE_FILE_SCOPE], "api", False),
        ("owner", [DRIVE_FILE_SCOPE], "compiler_gather", False),
        ("owner", [DRIVE_FILE_SCOPE], "protocol", False),
    ],
)
@pytest.mark.parametrize("kind", ["docs", "sheets"])
async def test_document_prepare_policy(tmp_path, role, scopes, source, allowed, kind):
    settings = Settings(_env_file=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    engine = create_async_engine(settings.resolved_database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    registry = ToolRegistry()
    for definition in document_tool_definitions() + spreadsheet_tool_definitions():
        assert definition.max_attempts == 1
        registry.register(definition)
    async with factory() as db:
        user = User(
            email="test@test.invalid",
            display_name="Test",
            role=role,
            oauth_scopes_json=json.dumps(scopes),
        )
        db.add(user)
        await db.commit()
        context = ToolContext(
            request_id="prepare", user=user, db=db, settings=settings, source=source
        )
        payload = {
            "request_key": "request-one",
            "action": "create",
            "document": {"title": "Report", "blocks": [{"text": "Hello"}]},
        }
        if kind == "sheets":
            payload = {
                "request_key": "sheet-request-one",
                "spreadsheet": {
                    "title": "Report",
                    "tabs": [{"title": "Data", "headers": ["A"], "rows": [[1]]}],
                },
            }
        if allowed:
            result = await registry.execute(kind + "_prepare", payload, context)
            assert result.data["state"] == "pending"
            if kind == "sheets":
                assert result.data["preview"]["spreadsheet"]["tabs"][0]["rows"] == [[1]]
            else:
                assert result.data["preview"] == {
                    **payload,
                    "patch": None,
                    "document": {
                        "title": "Report",
                        "blocks": [{"text": "Hello", "style": "NORMAL_TEXT"}],
                    },
                }
        else:
            with pytest.raises(ToolAccessDeniedError):
                await registry.execute(kind + "_prepare", payload, context)
    await engine.dispose()
