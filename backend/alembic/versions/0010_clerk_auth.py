"""clerk auth: wipe demo users, drop refresh_tokens + password_hash, add clerk_user_id

Revision ID: 0010_clerk_auth
Revises: 0009_notif_audit_disputes
Create Date: 2026-10-29 00:00:00.000000

The downgrade recreates refresh_tokens and password_hash but LOSES the Clerk
linkage recorded in users.clerk_user_id — any Clerk-provisioned users left
in the DB will no longer be reachable through the auth path once downgraded.
Only run it in dev.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_clerk_auth"
down_revision = "0009_notif_audit_disputes"
branch_labels = None
depends_on = None


_DEMO_EMAILS = (
    "demo-brand@test.local",
    "demo-creator@test.local",
    "admin@test.local",
)


def upgrade() -> None:
    bind = op.get_bind()

    # 1) Refuse the migration if there is any non-demo user to protect.
    non_demo = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM users "
            "WHERE email NOT IN :demo_emails"
        ).bindparams(sa.bindparam("demo_emails", expanding=True)),
        {"demo_emails": list(_DEMO_EMAILS)},
    ).scalar_one()
    if non_demo and non_demo > 0:
        raise RuntimeError(
            "Refusing to run 0010_clerk_auth: "
            f"{non_demo} non-demo user row(s) exist. "
            "Export + re-provision these accounts in Clerk, then re-run."
        )

    # 2) Wipe users (cascade removes dependent rows across the schema).
    op.execute(sa.text("TRUNCATE TABLE users CASCADE"))

    # 3) Drop the self-hosted refresh_tokens table and its index.
    op.drop_index(
        "ix_refresh_tokens_user_id_jti", table_name="refresh_tokens"
    )
    op.drop_table("refresh_tokens")

    # 4) Drop password_hash — Clerk owns credentials now.
    op.drop_column("users", "password_hash")

    # 5) role must be nullable so newly-provisioned Clerk users can land
    #    without a role until they pick one via /users/me/role.
    op.alter_column("users", "role", existing_type=postgresql.ENUM(
        "creator", "brand", "admin", name="user_role_enum", create_type=False,
    ), nullable=True)

    # 6) Add clerk_user_id as the canonical external identity.
    op.add_column(
        "users",
        sa.Column("clerk_user_id", sa.String(length=255), nullable=False),
    )
    op.create_unique_constraint(
        "uq_users_clerk_user_id", "users", ["clerk_user_id"]
    )
    op.create_index(
        "ix_users_clerk_user_id", "users", ["clerk_user_id"], unique=False
    )

    # 7) Replace the plain unique(email) with a partial unique index that
    #    only enforces uniqueness among active rows. Deactivated users may
    #    retain their email even if a new Clerk account reuses it.
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX ix_users_email_active "
            "ON users (email) WHERE is_active = true"
        )
    )


def downgrade() -> None:
    """Reverse the Clerk migration. LOSES Clerk linkage recorded in users."""

    # Reverse step 7: drop partial unique index, restore plain unique(email).
    op.execute(sa.text("DROP INDEX IF EXISTS ix_users_email_active"))
    op.create_unique_constraint("uq_users_email", "users", ["email"])

    # Reverse step 6: drop clerk_user_id.
    op.drop_index("ix_users_clerk_user_id", table_name="users")
    op.drop_constraint("uq_users_clerk_user_id", "users", type_="unique")
    op.drop_column("users", "clerk_user_id")

    # Reverse step 5: role becomes non-nullable again.
    op.alter_column(
        "users",
        "role",
        existing_type=postgresql.ENUM(
            "creator", "brand", "admin", name="user_role_enum", create_type=False,
        ),
        nullable=False,
    )

    # Reverse step 4: add password_hash NOT NULL (with transient empty default
    # so existing rows survive the DDL; immediately clear the default).
    op.add_column(
        "users",
        sa.Column(
            "password_hash",
            sa.String(length=255),
            nullable=False,
            server_default="",
        ),
    )
    op.alter_column("users", "password_hash", server_default=None)

    # Reverse step 3: recreate refresh_tokens with the 0002_users schema.
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_tokens"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_refresh_tokens_user_id_users",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("jti", name="uq_refresh_tokens_jti"),
    )
    op.create_index(
        "ix_refresh_tokens_user_id_jti",
        "refresh_tokens",
        ["user_id", "jti"],
        unique=False,
    )

    # No step-2 reverse — users remain wiped. Operators must re-seed.
