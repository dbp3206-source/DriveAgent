# Content Outline — Dữ liệu đã lưu

## Automatic reminder
- Header: Dữ liệu Veridra đã quá 30 ngày
- Measured total and item categories from the current preview
- Consequence: selected Veridra records and assistant working context will be removed
- Boundary: Gmail/Drive/Calendar/Docs originals stay in Google
- Actions: Để sau; confirm only after an unchecked-by-default checkbox is selected

## Job status
- States: queued, running, purging, succeeded, needs attention, cancelled
- Measured completed and remaining record counts
- Retry uses the already confirmed fixed scope; cancellation only before purge begins
- On success, clear local cached views of data that Veridra removed and preserve user drafts

## Settings entry
- State clearly: records become eligible after 30 days; deletion waits for confirmation
- Button: Kiểm tra dữ liệu cần dọn
- Show current job or a measured no-data result
