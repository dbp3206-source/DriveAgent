"""One-shot data sanitization for DriveAgent.

Run once to clean up known historical data issues:
  1. P0-02: Label the incorrect "0 ÷ 0 = 7" message with a warning banner
  2. P2-09: Remove RAG chunks contaminated with HTML asset comments
  3. P2-07: Archive orphaned Slides operations

Usage:
    python scripts/sanitize_history.py [--dry-run]
"""

import argparse
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MAIN_DB = DATA_DIR / "drive_agent.db"
OPS_DB = DATA_DIR / "operations.db"

WARNING_BANNER = (
    "\n\n> ⚠️ **Bản ghi lịch sử** — Kết quả tính toán này chứa lỗi "
    "đã được khắc phục trong phiên bản hiện tại. Phép chia cho 0 không xác định."
)

BAD_MSG_ID = "4a65c91c-b276-48d0-b36d-9bf0c76db461"


def sanitize_main_db(dry_run: bool) -> dict:
    """Fix issues in drive_agent.db."""
    stats = {"p0_02_labeled": 0, "p2_09_chunks_removed": 0}

    if not MAIN_DB.exists():
        print(f"[SKIP] {MAIN_DB} not found")
        return stats

    conn = sqlite3.connect(str(MAIN_DB))
    conn.row_factory = sqlite3.Row

    # --- P0-02: Label the "0 / 0 = 7" message ---
    row = conn.execute("SELECT id, content FROM messages WHERE id = ?", (BAD_MSG_ID,)).fetchone()
    if row:
        content = row["content"]
        if "⚠️" not in content:
            if not dry_run:
                conn.execute(
                    "UPDATE messages SET content = ? WHERE id = ?",
                    (content + WARNING_BANNER, BAD_MSG_ID),
                )
            stats["p0_02_labeled"] = 1
            print(f"[P0-02] {'Would label' if dry_run else 'Labeled'} message {BAD_MSG_ID}")
        else:
            print(f"[P0-02] Message {BAD_MSG_ID} already has warning -- skipping")
    else:
        print(f"[P0-02] Message {BAD_MSG_ID} not found -- skipping")

    # --- P2-09: Remove RAG chunks contaminated with asset HTML comments ---
    contaminated = conn.execute(
        "SELECT id, file_name, chunk_index FROM document_chunks "
        "WHERE content LIKE '%<!-- DriveAgent assets:%'"
    ).fetchall()
    for chunk in contaminated:
        if not dry_run:
            conn.execute("DELETE FROM document_chunks WHERE id = ?", (chunk["id"],))
        stats["p2_09_chunks_removed"] += 1
        print(
            f"[P2-09] {'Would remove' if dry_run else 'Removed'} contaminated chunk "
            f"{chunk['id']} (file={chunk['file_name']}, index={chunk['chunk_index']})"
        )

    if not contaminated:
        print("[P2-09] No contaminated RAG chunks found")

    if not dry_run:
        conn.commit()
    conn.close()
    return stats


def sanitize_ops_db(dry_run: bool) -> dict:
    """Archive orphaned Slides operations in operations.db."""
    stats = {"p2_07_archived": 0}

    if not OPS_DB.exists():
        print(f"[SKIP] {OPS_DB} not found")
        return stats

    conn = sqlite3.connect(str(OPS_DB))

    orphans = conn.execute(
        "SELECT id, capability FROM operations "
        "WHERE capability LIKE 'slides_%' AND (archived IS NULL OR archived = 0)"
    ).fetchall()
    for op_id, capability in orphans:
        if not dry_run:
            conn.execute("UPDATE operations SET archived = 1 WHERE id = ?", (op_id,))
        stats["p2_07_archived"] += 1
        action = "Would archive" if dry_run else "Archived"
        print(f"[P2-07] {action} operation {op_id} ({capability})")

    if not orphans:
        print("[P2-07] No orphaned Slides operations found")

    if not dry_run:
        conn.commit()
    conn.close()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Sanitize DriveAgent historical data")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying data",
    )
    args = parser.parse_args()

    print("=" * 60)
    print(f"DriveAgent Data Sanitization {'(DRY RUN)' if args.dry_run else ''}")
    print("=" * 60)
    print()

    main_stats = sanitize_main_db(args.dry_run)
    print()
    ops_stats = sanitize_ops_db(args.dry_run)
    print()

    all_stats = {**main_stats, **ops_stats}
    print("=" * 60)
    print("Summary:")
    for key, value in all_stats.items():
        print(f"  {key}: {value}")

    total_changes = sum(all_stats.values())
    if total_changes == 0:
        print("\nNo changes needed -- database is clean.")
    elif args.dry_run:
        print(f"\n{total_changes} change(s) would be made. Run without --dry-run to apply.")
    else:
        print(f"\n{total_changes} change(s) applied successfully.")


if __name__ == "__main__":
    main()
