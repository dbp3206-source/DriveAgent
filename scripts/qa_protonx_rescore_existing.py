"""Rescore preserved ProtonX output after correcting an over-strict evaluator rule."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from protonx_scoring import score_report_structure, summarize_structure

ROOT = Path(__file__).resolve().parents[1]
RESULT_PATH = ROOT / "design-work" / "qa" / "protonx-live-benchmark-20260925.json"
OUTPUT_DIR = ROOT / "design-work" / "qa"
BENCHMARK_PATH = ROOT / "backend" / "evals" / "protonx_company_benchmark.json"


def main() -> None:
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    required_fields = benchmark["required_report_fields"]
    scores: list[dict[str, object]] = []
    for case in benchmark["cases"]:
        case_id = case["id"]
        report = result["reports"][case_id]
        sources = result["sources"][case_id]
        score = score_report_structure(
            case_id, report, sources, required_fields,
            benchmark["release_thresholds"]["report_completeness"],
        )
        score["company"] = case["company"]
        scores.append(score)
    passed_count = sum(score["structural_pass"] for score in scores)
    result["scores"] = scores
    result.update(summarize_structure(scores))
    result["rescore_note"] = "Chỉ kiểm cấu trúc bản báo cáo cũ; không có lần chạy nghiệp vụ mới."
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"protonx-rescore-{stamp}.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# ProtonX six-company live benchmark",
        "",
        f"- Model: `{result['model']}`",
        f"- Cấu trúc đạt: **{passed_count}/{len(scores)}**",
        "- Chưa đo tỷ lệ hoàn thành nghiệp vụ; cần chạy quy trình đầy đủ.",
        f"- Latency toàn batch: **{result['latency_seconds']:.2f}s** (số đo toàn đợt, không phải mỗi yêu cầu)",
        "- Chưa có bằng chứng đo hành động ngoài ý muốn.",
        "- Nghiệm thu toàn sản phẩm: chưa kiểm chứng.",
        "- Có nhãn nguồn không chứng minh nhận định được nguồn xác nhận.",
        "- Bản trả lời được giữ để đối soát; chưa chứng minh duyệt/thực hiện/đọc lại.",
        "",
        "| Mẫu | Công ty | Nguồn | Đủ trường | Có nhãn nguồn chính | Nhãn nguồn hợp lệ | Cấu trúc |",
        "|---|---|---:|---:|---|---|---|",
    ]
    for score in scores:
        lines.append(
            f"| {score['case_id']} | {score['company']} | {score['source_count']} | "
            f"{score['completeness']:.0%} | {'PASS' if score['official_reference_present'] else 'FAIL'} | "
            f"{'PASS' if score['valid_citations'] else 'FAIL'} | "
            f"{'PASS' if score['structural_pass'] else 'FAIL'} |"
        )
    output_path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"gate_pass": result["gate_pass"], "structurally_passed_cases": passed_count}))


if __name__ == "__main__":
    main()
