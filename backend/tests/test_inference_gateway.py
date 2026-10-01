from types import SimpleNamespace

import pytest

from app.services.inference_gateway import (
    ProviderCircuitStore,
    RequestPinningGate,
    create_inference_client,
    provider_error_class,
)
from app.tools.contracts import ToolError


class ProviderFailure(Exception):
    def __init__(self, code: int, message: str = "provider failure"):
        super().__init__(message)
        self.code = code


def test_provider_error_class_is_bounded():
    assert provider_error_class(ProviderFailure(401))[0] == "authentication"
    assert provider_error_class(ProviderFailure(429))[0] == "quota"
    assert provider_error_class(ProviderFailure(503))[0] == "availability"
    assert provider_error_class(RuntimeError("unknown"))[0] == "provider"


def test_quota_opens_only_credential_scoped_circuit(tmp_path):
    first = ProviderCircuitStore(tmp_path / "provider.db", "secret-a")
    second = ProviderCircuitStore(tmp_path / "provider.db", "secret-b")
    first.failure("generate", ProviderFailure(429), now=100)
    with pytest.raises(ToolError, match="tạm nghỉ") as caught:
        first.before_request("generate", now=101)
    assert caught.value.code == "gemini_circuit_open"
    second.before_request("generate", now=101)
    assert first.snapshot(now=101)[0]["retry_after_seconds"] == 59


def test_availability_requires_three_failures_and_success_resets(tmp_path):
    circuit = ProviderCircuitStore(tmp_path / "provider.db", "secret")
    circuit.failure("generate", ProviderFailure(503), now=10)
    circuit.failure("generate", ProviderFailure(503), now=11)
    circuit.before_request("generate", now=12)
    circuit.failure("generate", ProviderFailure(503), now=12)
    with pytest.raises(ToolError):
        circuit.before_request("generate", now=13)
    circuit.success("generate", now=14)
    circuit.before_request("generate", now=14)
    assert circuit.snapshot(now=14)[0]["consecutive_failures"] == 0


@pytest.mark.asyncio
async def test_gateway_records_async_success_and_never_persists_secret(tmp_path):
    class Models:
        async def generate_content(self, **_kwargs):
            return SimpleNamespace(text="ok")

    class Aio:
        models = Models()

        async def aclose(self):
            return None

    class Client:
        def __init__(self, **_kwargs):
            self.aio = Aio()

        def close(self):
            return None

    secret = "sensitive-key-that-must-not-be-stored"
    client = create_inference_client(
        api_key=secret,
        data_dir=tmp_path,
        client_factory=Client,
    )
    response = await client.aio.models.generate_content(model="test", contents="hello")
    assert response.text == "ok"
    assert secret.encode() not in (tmp_path / "provider_state.db").read_bytes()
    await client.aio.aclose()
    client.close()


@pytest.mark.asyncio
async def test_gateway_records_async_failure_and_opens_quota_circuit(tmp_path):
    class Models:
        async def generate_content(self, **_kwargs):
            raise ProviderFailure(429, "quota exhausted")

    class Aio:
        models = Models()

        async def aclose(self):
            return None

    class Client:
        def __init__(self, **_kwargs):
            self.aio = Aio()

    client = create_inference_client(
        api_key="another-sensitive-key-value",
        data_dir=tmp_path,
        client_factory=Client,
    )
    with pytest.raises(ProviderFailure):
        await client.aio.models.generate_content(model="test", contents="hello")
    with pytest.raises(ToolError) as caught:
        await client.aio.models.generate_content(model="test", contents="hello")
    assert caught.value.code == "gemini_circuit_open"
    client.close()


@pytest.mark.asyncio
async def test_gateway_isolates_grounding_quota_from_plain_generation(tmp_path):
    class Models:
        async def generate_content(self, **_kwargs):
            raise ProviderFailure(429, "grounding quota exhausted")

    class Aio:
        models = Models()

        async def aclose(self):
            return None

    class Client:
        def __init__(self, **_kwargs):
            self.aio = Aio()

        def close(self):
            return None

    secret = "capability-isolated-sensitive-key"
    grounding = create_inference_client(
        api_key=secret,
        data_dir=tmp_path,
        client_factory=Client,
        async_capability="web_grounding",
    )
    with pytest.raises(ProviderFailure):
        await grounding.aio.models.generate_content(model="test", contents="hello")

    circuit = ProviderCircuitStore(tmp_path / "provider_state.db", secret)
    with pytest.raises(ToolError):
        circuit.before_request("web_grounding")
    circuit.before_request("generate")
    grounding.close()


def test_gateway_wraps_sync_embedding_success_and_failure(tmp_path):
    class Models:
        fail = False

        def embed_content(self, **_kwargs):
            if self.fail:
                raise ProviderFailure(503)
            return SimpleNamespace(embeddings=[[0.1, 0.2]])

    class Client:
        def __init__(self, **_kwargs):
            self.models = Models()
            self.aio = SimpleNamespace(models=SimpleNamespace())

    client = create_inference_client(
        api_key="embedding-sensitive-key",
        data_dir=tmp_path,
        client_factory=Client,
    )
    assert client.models.embed_content(model="embedding", contents="text").embeddings
    client._client.models.fail = True
    with pytest.raises(ProviderFailure):
        client.models.embed_content(model="embedding", contents="text")
    assert client._client.models.fail is True


@pytest.mark.asyncio
async def test_request_pinning_waits_for_active_request_before_switch():
    import asyncio

    gate = RequestPinningGate()
    entered = asyncio.Event()
    release = asyncio.Event()
    switched = asyncio.Event()

    async def active_request():
        async with gate.request("owner"):
            entered.set()
            await release.wait()

    async def rotate():
        async with gate.switch():
            switched.set()

    request_task = asyncio.create_task(active_request())
    await entered.wait()
    rotate_task = asyncio.create_task(rotate())
    await asyncio.sleep(0)
    assert not switched.is_set()
    release.set()
    await request_task
    await rotate_task
    assert switched.is_set()


@pytest.mark.asyncio
async def test_request_pinning_switch_does_not_deadlock_on_prolonged_request():
    import asyncio

    gate = RequestPinningGate()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def prolonged_request():
        async with gate.request():
            entered.set()
            await release.wait()

    request_task = asyncio.create_task(prolonged_request())
    await entered.wait()

    # An active client must never be closed after a timed-out switch.
    with pytest.raises(TimeoutError, match="Active inference"):
        async with gate.switch(timeout=0.05):
            pass

    release.set()
    await request_task


@pytest.mark.asyncio
async def test_retired_runtime_closes_only_after_pinned_request_finishes():
    import asyncio
    from unittest.mock import AsyncMock

    gate = RequestPinningGate()
    entered = asyncio.Event()
    release = asyncio.Event()
    close = AsyncMock()

    async def active_request():
        async with gate.request("owner"):
            entered.set()
            await release.wait()

    task = asyncio.create_task(active_request())
    await entered.wait()
    await gate.retire("owner", close)
    close.assert_not_awaited()
    release.set()
    await task
    close.assert_awaited_once()


@pytest.mark.asyncio
async def test_retirement_is_scoped_to_user_not_other_active_chat():
    import asyncio
    from unittest.mock import AsyncMock

    gate = RequestPinningGate()
    entered = asyncio.Event()
    release = asyncio.Event()
    close_alice = AsyncMock()
    close_bob = AsyncMock()

    async def alice_request():
        async with gate.request("alice"):
            entered.set()
            await release.wait()

    task = asyncio.create_task(alice_request())
    await entered.wait()
    await gate.retire("alice", close_alice)
    await gate.retire("bob", close_bob)
    close_alice.assert_not_awaited()
    close_bob.assert_awaited_once()
    release.set()
    await task
    close_alice.assert_awaited_once()
