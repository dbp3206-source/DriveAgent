from types import SimpleNamespace

from app.api.dependencies import is_trusted_ui_origin
from app.core.config import Settings


def _request(**headers: str) -> SimpleNamespace:
    return SimpleNamespace(headers={key.replace("_", "-"): value for key, value in headers.items()})


def test_production_write_origin_requires_exact_trusted_origin():
    settings = Settings(
        _env_file=None,
        environment="production",
        frontend_origin="https://veridra.example",
        public_base_url="https://veridra.example",
    )
    assert is_trusted_ui_origin(_request(origin="https://veridra.example"), settings)
    assert is_trusted_ui_origin(
        _request(referer="https://veridra.example/chat?tab=1"), settings
    )
    assert not is_trusted_ui_origin(
        _request(referer="https://veridra.example.evil.test/attack"), settings
    )
    assert not is_trusted_ui_origin(
        _request(origin="https://evil.test", referer="https://veridra.example/chat"), settings
    )
    assert not is_trusted_ui_origin(
        _request(x_requested_with="XMLHttpRequest", sec_fetch_site="same-origin"), settings
    )
    assert not is_trusted_ui_origin(_request(host="localhost:8000"), settings)
    assert not is_trusted_ui_origin(_request(origin="null"), settings)
    assert not is_trusted_ui_origin(_request(origin="https://veridra.example/path"), settings)
    assert not is_trusted_ui_origin(_request(origin="https://[invalid"), settings)


def test_local_write_origin_keeps_loopback_browser_flow():
    settings = Settings(_env_file=None, environment="development")
    assert is_trusted_ui_origin(_request(origin="http://localhost:8000"), settings)
    assert is_trusted_ui_origin(_request(host="localhost:8000"), settings)
    assert is_trusted_ui_origin(_request(x_requested_with="XMLHttpRequest"), settings)
    assert not is_trusted_ui_origin(
        _request(origin="https://evil.test", host="localhost:8000"), settings
    )
