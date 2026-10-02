import subprocess
import sys
from pathlib import Path


def test_cloud_vector_backend_does_not_import_qdrant():
    backend = Path(__file__).resolve().parents[1]
    script = (
        "import asyncio,sys; from types import SimpleNamespace; "
        "from app.services.vector_store import VectorStore; "
        "url='postgresql+psycopg://test.invalid/qa'; "
        "v=VectorStore(SimpleNamespace(resolved_database_url=url)); "
        "asyncio.run(v.initialize()); "
        "assert v.backend_name == 'postgres-pgvector'; "
        "assert 'qdrant_client' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=backend,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
