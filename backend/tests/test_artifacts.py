from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings
from app.db.models import Base, User
from app.services.artifacts import ArtifactListInput, ArtifactWrite, list_artifacts, save_artifact
from app.tools.contracts import ToolContext, ToolError


@pytest.mark.parametrize("field", ["title", "content"])
@pytest.mark.parametrize("blank", [" ", "\n\t", "\u00a0"])
def test_artifact_rejects_whitespace_only(field, blank):
    values = {"title": "Ghi chú", "content": "Nội dung", "creation_key": uuid4()}
    values[field] = blank
    with pytest.raises(ValidationError):
        ArtifactWrite.model_validate(values)


def test_artifact_preserves_markdown_indentation():
    content = "\n    print('example')\n"
    payload = ArtifactWrite(title="Ví dụ", content=content, creation_key=uuid4())
    assert payload.content == content


@pytest.mark.asyncio
async def test_artifact_tenant_revision_and_retry(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'artifacts.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        a = User(email="a@test.invalid", display_name="A", role="editor")
        b = User(email="b@test.invalid", display_name="B", role="editor")
        db.add_all([a, b])
        await db.commit()
        a_id = a.id
        ctx = ToolContext(request_id="test", user=a, db=db, settings=Settings(_env_file=None))
        payload = ArtifactWrite(title="Ôn tập", content="- [ ] Chương 1", creation_key=uuid4())
        item = await save_artifact(payload, ctx)
        await db.commit()
        assert (await save_artifact(payload, ctx)).id == item.id
        ctx.user = b
        assert (await list_artifacts(ArtifactListInput(), ctx)).items == []
        edit = payload.model_copy(update={"artifact_id": item.id, "content": "Đã sửa"})
        with pytest.raises(ToolError):
            await save_artifact(edit, ctx)
        await db.rollback()
        ctx.user = await db.get(User, a_id)
        edited = await save_artifact(edit, ctx)
        assert edited.revision == 2
        await db.commit()
        with pytest.raises(ToolError):
            await save_artifact(edit, ctx)
    await engine.dispose()
