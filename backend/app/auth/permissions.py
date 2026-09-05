"""RBAC của ứng dụng, tách biệt với OAuth scopes của Google.

RBAC trả lời "người dùng được dùng tool nào trong DriveAgent". OAuth scope trả lời
"Google đã cấp token này quyền gì". Một tool Drive chỉ chạy khi cả hai lớp đều cho phép.
"""

from app.db.models import UserRole

DRIVE_READ = "drive:read"
DRIVE_WRITE = "drive:write"
RAG_READ = "rag:read"
RAG_WRITE = "rag:write"
MEMORY_READ = "memory:read"
MEMORY_WRITE = "memory:write"
AUDIT_READ_SELF = "audit:read:self"
AUDIT_READ_ALL = "audit:read:all"
USER_MANAGE = "users:manage"

ROLE_PERMISSIONS: dict[str, set[str]] = {
    UserRole.VIEWER.value: {DRIVE_READ, RAG_READ, MEMORY_READ, AUDIT_READ_SELF},
    UserRole.EDITOR.value: {
        DRIVE_READ,
        RAG_READ,
        RAG_WRITE,
        MEMORY_READ,
        MEMORY_WRITE,
        AUDIT_READ_SELF,
    },
    UserRole.OWNER.value: {
        DRIVE_READ,
        DRIVE_WRITE,
        RAG_READ,
        RAG_WRITE,
        MEMORY_READ,
        MEMORY_WRITE,
        AUDIT_READ_SELF,
    },
    UserRole.SUPER_ADMIN.value: {
        DRIVE_READ,
        DRIVE_WRITE,
        RAG_READ,
        RAG_WRITE,
        MEMORY_READ,
        MEMORY_WRITE,
        AUDIT_READ_SELF,
        AUDIT_READ_ALL,
        USER_MANAGE,
    },
}


def permissions_for_role(role: str) -> set[str]:
    return ROLE_PERMISSIONS.get(role, set())
