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


@pytest.mark.asyncio
async def test_saved_report_survives_reopen_and_archive_without_losing_source(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'durable-artifacts.db'}"
    engine = create_async_engine(url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    content = (
        "## Hồ sơ khách hàng mẫu\n\nNgân sách chưa biết.\n\n"
        "| Hạng mục | Số lượng |\n| --- | --- |\n| Nhân viên | 42 |\n\n"
        "Nguồn: [Tài liệu mẫu](https://example.com/source) [1]"
    )
    async with factory() as db:
        owner = User(email="durable@example.test", display_name="QA", role="editor")
        db.add(owner)
        await db.flush()
        owner_id = owner.id
        ctx = ToolContext(request_id="save", user=owner, db=db, settings=Settings(_env_file=None))
        payload = ArtifactWrite(title="Báo cáo tư vấn mẫu", content=content,
                                kind="report", creation_key=uuid4())
        saved = await save_artifact(payload, ctx)
        await db.commit()
        artifact_id = saved.id
    await engine.dispose()

    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as db:
            owner = await db.get(User, owner_id)
            ctx = ToolContext(request_id="read", user=owner, db=db,
                              settings=Settings(_env_file=None))
            items = (await list_artifacts(ArtifactListInput(), ctx)).items
            assert len(items) == 1
            assert items[0].id == artifact_id
            assert items[0].content == content
            archive = payload.model_copy(update={"artifact_id": artifact_id, "is_archived": True})
            archived = await save_artifact(archive, ctx)
            await db.commit()
            assert archived.revision == 2
            assert (await list_artifacts(ArtifactListInput(), ctx)).items == []
            visible = (await list_artifacts(ArtifactListInput(include_archived=True), ctx)).items
            assert visible[0].content == content
            restored = await save_artifact(archive.model_copy(update={
                "is_archived": False, "expected_revision": 2,
            }), ctx)
            await db.commit()
            assert restored.revision == 3
            assert restored.content == content
    finally:
        await engine.dispose()
