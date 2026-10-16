# Design Brief

## Audience and viewing context
Signed-in Veridra users, on desktop or mobile, receive an occasional notice while using the app and can review it later in Settings.

## Core message
Veridra keeps its own working data for 30 days and asks the user before removing anything.

## Desired reaction or action
Understand the exact count and scope, then confirm, postpone, or review the cleanup status.

## Source authority
`backend/app/services/retention_policy.py`, `backend/app/services/retention_coordinator.py`, `backend/app/api/retention.py`, and the product decision recorded in this task: 30-day retention, a visible notice, and explicit confirmation before deletion.

## Content hierarchy
1. What Veridra data is due for cleanup and its measured count.
2. The consequence of approval, including resetting assistant context.
3. The boundary: source Gmail, Drive, Calendar, and Google Docs remain unchanged.
4. Confirm, postpone, and current job status.

## Visual territory
Use the existing Fluent UI 9 component system, app theme, typography, and status colors. Keep the reminder calm and compact; use one confirmation surface and measured status feedback.

## Brand and system constraints
Preserve the existing light/dark theme, Be Vietnam Pro font, Fluent Dialog, Button, Checkbox, Badge, MessageBar, and app spacing tokens. Support keyboard focus and narrow viewports.

## Anti-goals
No new visual style, new dependency, decorative mascot artwork, fabricated counts, forced navigation, deletion without a checked confirmation, or wording that implies Google originals are deleted.

## Output contract
Editable React/TypeScript components and stylesheet within the existing app. Verify the real app at desktop and mobile viewports with screenshots and record findings in this task's QA directory.

## Reference interpretation
The current Settings page and Fluent UI 9 are the reference. Reuse their dialog, button, message, and theme treatment rather than introducing a separate template.
