import pytest

from app.core.source_pages import explicit_page_numbers


@pytest.mark.parametrize(("message", "expected"), [
    ("Đối chiếu bảng và nhận định ngay cùng dòng ở trang 2.", (2,)),
    ("Xem trang số 7 và 9, rồi trang 7.", (7, 9)),
    ("Đọc trang 2 đến 4.", (2, 3, 4)),
    ("Read physical PDF pages 8–10 and 12.", (8, 9, 10, 12)),
    ("Read p. 3.", (3,)),
    ("Đọc trang 2; không đọc trang 11.", (2,)),
    ("Không dùng trang 2; chỉ đọc trang 3.", (3,)),
    ("Read page 4. Do not read page 8.", (4,)),
    ("Tăng 12% vào 3/5/2026; report_20260408.pdf.", ()),
    ("Có 12 trang trong tài liệu.", ()),
])
def test_numeric_page_constraints(message, expected):
    assert explicit_page_numbers(message) == expected


@pytest.mark.parametrize("message", ["Read pages 2-100000000", "trang 0", "pages 9-2"])
def test_invalid_or_excessive_page_constraints_fail_closed(message):
    with pytest.raises(ValueError):
        explicit_page_numbers(message)
