"""Revision-guarded update of the saved daily Gmail skill procedure.

Prior procedures remain below for a manual rollback. No Gmail, Drive, model,
or external API request is made by this local migration.
"""

from __future__ import annotations

import argparse
import json

from app.db.session import settings
from app.services.skills import SkillSpec, SkillStore
from qa_google_read_smoke import _connected_owner_id

OLD_STEPS = [
    (
        'Lấy ngày và thời điểm hiện tại theo múi giờ Asia/Bangkok. Tìm Gmail trong 48 giờ '
        'gần nhất với from:"Bảo Phúc Đinh" subject:"Bản chi tiết"; nếu không thấy, tìm '
        'theo subject rồi xác minh người gửi từ header. Dùng phân trang đến khi hết kết quả.'
    ),
    (
        'Đọc toàn bộ nội dung từng thread phù hợp; chỉ giữ thư có người gửi xác minh '
        'được là Bảo Phúc Đinh, ngày nhận là hôm nay theo Asia/Bangkok và thời gian '
        'không vượt quá thời điểm chạy. Không dùng snippet làm nội dung tóm tắt.'
    ),
    (
        'Đối chiếu các mốc dự kiến 08:00, 12:00, 15:00, 21:00; nêu mốc đã có, '
        'mốc chưa tới và mốc đến giờ nhưng chưa tìm thấy. Không coi thư không truy cập '
        'được là thư không tồn tại.'
    ),
]
NEW_STEPS = [
    (
        'Lấy ngày và thời điểm hiện tại theo Asia/Bangkok. Gọi gmail_read_matching_messages '
        'với from:"Bảo Phúc Đinh" subject:"Bản chi tiết", local_date là hôm nay, timezone '
        'Asia/Bangkok và sender_name là "Bảo Phúc Đinh"; kiểm next_page_token cho đến khi hết. '
        'Nếu truy vấn người gửi không thấy thư, tìm theo subject nhưng vẫn lọc '
        'sender_name từ header.'
    ),
    (
        'Dùng body đầy đủ đã đọc của từng thư phù hợp; chỉ giữ thư có người gửi xác minh '
        'được là Bảo Phúc Đinh, ngày nhận là hôm nay theo Asia/Bangkok và thời gian không '
        'vượt quá thời điểm chạy. Chỉ mở thread riêng nếu body thiếu; không dùng snippet '
        'làm nội dung tóm tắt.'
    ),
    (
        'Đối chiếu bốn nhãn mốc 08:00, 12:00, 15:00, 21:00 trong tiêu đề với '
        'received_at_local và as_of_local của Gmail. Thư đã nhận thì luôn đưa vào dù '
        'nhãn mốc lớn hơn giờ hiện tại; với nhãn chưa có chỉ nói chưa tìm thấy trước thời '
        'điểm chạy, không tự kết luận thư chưa tới hạn hoặc gửi chậm. Không coi thư không '
        'truy cập được là thư không tồn tại.'
    ),
]
LATEST_STEPS = [
    *NEW_STEPS[:2],
    (
        'Đếm tất cả thư phù hợp có received_at_local trong ngày đang xét và không muộn '
        'hơn as_of_local. Báo số thư thực tế cùng thời điểm nhận, bất kể tiêu đề có nhãn '
        '8h, 12h hay nhãn khác; không ép đủ bốn mốc, không suy đoán thư sẽ đến sau. '
        'Không coi thư không truy cập được là thư không tồn tại.'
    ),
]
FINAL_STEPS = [
    (
        'Gọi gmail_read_matching_messages với from:"Bảo Phúc Đinh" '
        'subject:"Bản chi tiết", day_scope="today", timezone="Asia/Bangkok" và '
        'sender_name="Bảo Phúc Đinh"; để công cụ tự xác định ngày hiện tại, không tự '
        'tính local_date. Kiểm next_page_token cho đến khi hết. Nếu truy vấn người gửi '
        'không thấy thư, tìm theo subject nhưng vẫn lọc sender_name từ header; công cụ '
        'chấp nhận thứ tự tên Đinh Bảo Phúc tương đương.'
    ),
    *LATEST_STEPS[1:],
]
V5_STEPS = [
    FINAL_STEPS[0],
    (
        'Đọc toàn bộ body của từng thư phù hợp và chỉ tổng hợp nội dung có trong body. '
        'Dùng received_at_local chỉ để lọc theo ngày và as_of_local; không đưa giờ nhận '
        'riêng của từng thư vào báo cáo. Nhãn 8h/12h/15h/21h trong subject chỉ là nhãn, '
        'không phải giờ nhận. Không dùng snippet, không suy diễn giờ, số liệu hay kết luận.'
    ),
    (
        'Viết báo cáo tiếng Việt chi tiết, có cấu trúc theo chủ đề thay vì ép thành ba ý. '
        'Mở đầu bằng ngày, thời điểm chốt as_of_local và số thư thực tế đã đọc. Có thể '
        'nêu nhãn trong subject để định vị nguồn nhưng không gán nhãn đó thành giờ nhận. '
        'Phân tích các luận điểm, dữ kiện, nguyên nhân, tác động, điểm đồng thuận/khác biệt '
        'và điều chưa đủ bằng chứng; mỗi nhận định gắn citation của đúng email nguồn. '
        'Không gán citation của email này cho nội dung email khác.'
    ),
]
V6_STEPS = [
    FINAL_STEPS[0],
    V5_STEPS[1],
    (
        'Mở đầu bằng ngày, thời điểm chốt as_of_local và số thư thực tế. Tạo mục riêng cho '
        'từng email; giữ luận điểm chính, ý phụ trọng yếu, cơ chế/nguyên nhân, số liệu kèm '
        'điều kiện, trade-off/rủi ro và kết luận/hành động nguồn nêu. Thư dài phải có độ sâu '
        'tương ứng; không ép mọi thư thành ba ý hay một đoạn chủ đề chung.'
    ),
    (
        'Sau các mục nguồn, tổng hợp điểm giao nhau, khác biệt/mâu thuẫn và ý nghĩa thực '
        'tiễn. Gắn nhãn “Suy luận” cho diễn giải do Agent suy ra. Đặt citation đúng email '
        'ngay cạnh nhận định; không gom hoặc gán nguồn chéo. Giữ caveat và mức độ bằng chứng; '
        'không biến nội dung email thành sự thật đã xác minh độc lập.'
    ),
    (
        'Độ dài phải theo lượng thông tin, không giới hạn ở vài gạch đầu dòng. Với 3–5 thư '
        'dài, hướng tới 900–1.500 từ nếu nguồn có đủ nội dung quan trọng; không thêm chữ lặp '
        'để đạt số từ. Không tự cắt ngắn vì giả định trần output. Nếu không thể bao phủ hết, '
        'nêu rõ báo cáo còn thiếu và nhóm nội dung chưa xử lý; không tuyên bố hoàn tất giả.'
    ),
]
COUNT_CONSTRAINT = (
    'Số thư trong báo cáo là số tìm thấy và đọc được lúc chạy; không giả định mỗi ngày '
    'phải đủ bốn thư hay đúng giờ ghi trên tiêu đề.'
)
PRESENTATION_CONSTRAINT = (
    'Chỉ nêu thời điểm chốt báo cáo; không nêu giờ nhận riêng từng email. Chỉ dùng '
    'received_at_local để lọc, không suy ra giờ nhận từ nhãn subject 8h/12h/15h/21h.'
)
DEPTH_CONSTRAINT = (
    'Bản tin nhiều email phải có mục bao phủ từng nguồn, giữ lại luận điểm, số liệu, '
    'điều kiện và trade-off trọng yếu; có tổng hợp liên nguồn, citation chính xác và '
    'phân biệt suy luận. Không mặc định rút gọn thành ba ý hoặc giới hạn ngắn.'
)


def main(*, apply: bool) -> None:
    store = SkillStore(settings.data_dir)
    owner_id = _connected_owner_id()
    row = store.get(owner_id, "daily_news_brief")
    if (
        row["revision"] == 6
        and row["procedure"][:len(V6_STEPS)] == V6_STEPS
        and COUNT_CONSTRAINT in row["constraints"]
        and PRESENTATION_CONSTRAINT in row["constraints"]
        and DEPTH_CONSTRAINT in row["constraints"]
    ):
        print(json.dumps({"status": "already_current", "revision": row["revision"]}))
        return
    known_revision = (
        row["revision"] == 1 and row["procedure"][:3] == OLD_STEPS
    ) or (
        row["revision"] == 2 and row["procedure"][:3] == NEW_STEPS
    ) or (
        row["revision"] == 3 and row["procedure"][:3] == LATEST_STEPS
    ) or (
        row["revision"] == 4
        and row["procedure"][:3] == FINAL_STEPS
        and COUNT_CONSTRAINT in row["constraints"]
    ) or (
        row["revision"] == 5
        and row["procedure"][:3] == V5_STEPS
        and COUNT_CONSTRAINT in row["constraints"]
        and PRESENTATION_CONSTRAINT in row["constraints"]
    )
    if not known_revision:
        raise RuntimeError("Saved skill differs from known v1/v2/v3/v4; refusing to overwrite")
    changed_steps = len(V6_STEPS)
    if not apply:
        print(
            json.dumps(
                {"status": "ready", "revision": row["revision"], "steps_to_update": changed_steps}
            )
        )
        return
    spec_data = {name: row[name] for name in SkillSpec.model_fields}
    spec_data["procedure"] = [*V6_STEPS, *row["procedure"][3:]]
    if COUNT_CONSTRAINT not in spec_data["constraints"]:
        spec_data["constraints"] = [*spec_data["constraints"], COUNT_CONSTRAINT]
    if PRESENTATION_CONSTRAINT not in spec_data["constraints"]:
        spec_data["constraints"] = [*spec_data["constraints"], PRESENTATION_CONSTRAINT]
    if DEPTH_CONSTRAINT not in spec_data["constraints"]:
        spec_data["constraints"] = [*spec_data["constraints"], DEPTH_CONSTRAINT]
    saved = store.save(
        owner_id,
        SkillSpec.model_validate(spec_data),
        expected_revision=row["revision"],
    )
    print(
        json.dumps(
            {"status": "updated", "revision": saved["revision"], "steps_updated": changed_steps}
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit the guarded local update")
    args = parser.parse_args()
    main(apply=args.apply)
