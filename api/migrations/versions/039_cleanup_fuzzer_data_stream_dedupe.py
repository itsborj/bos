"""cleanup fuzzer data and enforce stream source_key dedupe

Revision ID: 039_cleanup_fuzzer_data_stream_dedupe
Revises: 038_plugin_activations
Create Date: 2026-06-10
"""
from alembic import op
import sqlalchemy as sa

revision = "039_cleanup_fuzzer_data_stream_dedupe"
down_revision = "038_plugin_activations"
branch_labels = None
depends_on = None


# Do not treat normal multiline text as fuzzer garbage. PostgreSQL's
# [[:cntrl:]] includes newlines/tabs, which are valid in descriptions/briefs.
# Match only replacement characters and non-whitespace ASCII controls.
_BAD_TEXT = r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]|�"


def upgrade() -> None:
    # Alembic creates alembic_version.version_num as VARCHAR(32) by default.
    # This revision id is longer than that, so widen the column before Alembic
    # records this migration as applied.
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(32),
        type_=sa.String(128),
        existing_nullable=False,
    )

    # Remove obvious Schemathesis/fuzzer rows that contain control/replacement
    # characters or Python sentinel names in user-visible text fields. These rows
    # were created by auth-enabled fuzz tests and should never appear in operator
    # lists.
    op.execute(sa.text("DELETE FROM calendar_pages WHERE slug ~ :bad OR title ~ :bad OR coalesce(description, '') ~ :bad").bindparams(bad=_BAD_TEXT))
    op.execute(sa.text("DELETE FROM brands WHERE name ~ :bad OR name = '__main__' OR brand_json::text ~ :bad").bindparams(bad=_BAD_TEXT))
    op.execute(sa.text("DELETE FROM campaigns WHERE name ~ :bad OR name = '__main__'").bindparams(bad=_BAD_TEXT))
    op.execute(sa.text("DELETE FROM objectives WHERE summary ~ :bad OR success_metric ~ :bad OR horizon ~ :bad OR created_from ~ :bad").bindparams(bad=_BAD_TEXT))
    op.execute(sa.text("DELETE FROM council_sessions WHERE brief ~ :bad OR coalesce(pending_c6_prompt, '') ~ :bad OR rounds::text ~ :bad OR c6_injections::text ~ :bad").bindparams(bad=_BAD_TEXT))

    # Collapse existing duplicate stream rows, keeping the oldest row for each
    # workspace/source_key, then prevent races from reintroducing duplicates.
    op.execute("""
        DELETE FROM stream_updates
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       row_number() OVER (
                           PARTITION BY workspace_id, source_key
                           ORDER BY created_at ASC, id ASC
                       ) AS rn
                FROM stream_updates
                WHERE source_key IS NOT NULL
            ) ranked
            WHERE ranked.rn > 1
        )
    """)
    op.create_index(
        "uq_stream_updates_workspace_source_key",
        "stream_updates",
        ["workspace_id", "source_key"],
        unique=True,
        postgresql_where=sa.text("source_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_stream_updates_workspace_source_key", table_name="stream_updates")
