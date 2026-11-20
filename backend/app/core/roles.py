"""Role helpers shared by deps, policies and routers.

V2 introduces ``student``, ``dept_admin``, ``hod`` and ``super_admin``. During the
expand phase of the migration the V1 values (``user``, ``admin``, ``management``)
still exist in the database, so every comparison goes through ``canonical_role``.
"""

# V1 role value -> V2 role value
V1_TO_V2 = {
    "user": "student",
    "admin": "super_admin",
    "management": "hod",
}

V2_ROLES = ("student", "staff", "dept_admin", "hod", "super_admin")

# Roles that must have exactly one / at least one department membership.
SINGLE_DEPARTMENT_ROLES = ("staff", "dept_admin")
MULTI_DEPARTMENT_ROLES = ("hod",)
NO_DEPARTMENT_ROLES = ("student", "super_admin")

# V1 roles that were global before department scoping existed. They stay global
# until the backfill (Part 3) converts them to V2 roles with explicit memberships.
LEGACY_GLOBAL_ROLES = ("admin", "management")


def role_value(role) -> str:
    return role.value if hasattr(role, "value") else str(role)


def canonical_role(role) -> str:
    value = role_value(role)
    return V1_TO_V2.get(value, value)


def has_role(user, *roles) -> bool:
    """True when the user's role matches any of ``roles`` (V1 or V2 names)."""
    allowed = {canonical_role(r) for r in roles}
    return canonical_role(user.role) in allowed
