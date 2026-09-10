import json

import pytest

from app.services.local_sources import extract_text
from app.tools.contracts import ToolError


def test_notebook_reads_source_not_outputs_or_executes():
    data = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["print('hello')"],
                "outputs": [{"text": "DO NOT INCLUDE"}],
            }
        ]
    }
    text = extract_text("test.ipynb", json.dumps(data).encode())
    assert text == "print('hello')"
    assert "DO NOT INCLUDE" not in text


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("test.exe", b"MZ"),
        ("test.txt", b"\xff"),
        ("test.txt", b"\x00"),
        ("test.ipynb", b"[]"),
        ("test.txt", b""),
        ("test.txt", b"a" * 100001),
        ("test.txt", b"a" * 2000001),
    ],
    ids=[
        "unsupported",
        "non_utf8",
        "binary",
        "invalid_notebook",
        "empty",
        "text_limit",
        "size_limit",
    ],
)
def test_invalid_imports(name, data):
    with pytest.raises(ToolError):
        extract_text(name, data)


def test_utf8_bom_and_formula_are_inert_text():
    assert extract_text("test.md", b"\xef\xbb\xbfhello") == "hello"
    assert extract_text("test.csv", b"name,value\nx,=1+1") == "name,value\nx,=1+1"
