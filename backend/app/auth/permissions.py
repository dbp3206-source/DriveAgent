"""RBAC của ứng dụng, tách biệt với OAuth scopes của Google.

RBAC trả lời "người dùng được dùng tool nào trong DriveAgent". OAuth scope trả lời
"Google đã cấp token này quyền gì". Một tool Drive chỉ chạy khi cả hai lớp đều cho phép.
"""

from app.db.models import UserRole

DRIVE_READ = "drive:read"
DRIVE_WRITE = "drive:write"
GMAIL_READ = "gmail:read"
GMAIL_SEND = "gmail:send"
GMAIL_DRAFT = "gmail:draft"
RAG_READ = "rag:read"
RAG_WRITE = "rag:write"
MEMORY_READ = "memory:read"
MEMORY_WRITE = "memory:write"
AUDIT_READ_SELF = "audit:read:self"
AUDIT_READ_ALL = "audit:read:all"
USER_MANAGE = "users:manage"
ARTIFACT_WRITE = "artifact:write"
SKILL_MANAGE = "skills:manage"
WEB_RESEARCH = "web:research"
COMPANY_READ = "company:read"
COMPANY_WRITE = "company:write"
CALENDAR_READ = "calendar:read"
REPORT_EXPORT = "report:export"
PROVIDER_CREDENTIAL_MANAGE = "provider_credentials:manage"

ROLE_PERMISSIONS: dict[str, set[str]] = {
    UserRole.VIEWER.value: {
        DRIVE_READ,
        GMAIL_READ,
        RAG_READ,
        MEMORY_READ,
        AUDIT_READ_SELF,
        COMPANY_READ,
        CALENDAR_READ,
        WEB_RESEARCH,
    },
    UserRole.EDITOR.value: {
        DRIVE_READ,
        DRIVE_WRITE,
        GMAIL_READ,
        GMAIL_DRAFT,
        RAG_READ,
        RAG_WRITE,
        MEMORY_READ,
        MEMORY_WRITE,
        AUDIT_READ_SELF,
        ARTIFACT_WRITE,
        SKILL_MANAGE,
        WEB_RESEARCH,
        COMPANY_READ,
        COMPANY_WRITE,
        CALENDAR_READ,
        REPORT_EXPORT,
        PROVIDER_CREDENTIAL_MANAGE,
    },
    UserRole.OWNER.value: {
        DRIVE_READ,
        DRIVE_WRITE,
        GMAIL_READ,
        GMAIL_SEND,
        GMAIL_DRAFT,
        RAG_READ,
        RAG_WRITE,
        MEMORY_READ,
        MEMORY_WRITE,
        AUDIT_READ_SELF,
        ARTIFACT_WRITE,
        SKILL_MANAGE,
        WEB_RESEARCH,
        COMPANY_READ,
        COMPANY_WRITE,
        CALENDAR_READ,
        REPORT_EXPORT,
        PROVIDER_CREDENTIAL_MANAGE,
    },
    UserRole.SUPER_ADMIN.value: {
        DRIVE_READ,
        DRIVE_WRITE,
        GMAIL_READ,
        GMAIL_SEND,
        GMAIL_DRAFT,
        RAG_READ,
        RAG_WRITE,
        MEMORY_READ,
        MEMORY_WRITE,
        AUDIT_READ_SELF,
        AUDIT_READ_ALL,
        USER_MANAGE,
        ARTIFACT_WRITE,
        SKILL_MANAGE,
        WEB_RESEARCH,
        COMPANY_READ,
        COMPANY_WRITE,
        CALENDAR_READ,
        REPORT_EXPORT,
        PROVIDER_CREDENTIAL_MANAGE,
    },
}


def permissions_for_role(role: str) -> set[str]:
    return ROLE_PERMISSIONS.get(role, set())
