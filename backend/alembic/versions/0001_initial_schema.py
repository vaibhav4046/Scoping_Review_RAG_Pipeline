"""Initial schema — all 8 tables + pgvector extension.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2025-01-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(128), nullable=False),
        sa.Column("full_name", sa.String(256), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ── reviews ───────────────────────────────────────────────────────────────
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("search_query", sa.Text(), nullable=True),
        sa.Column("inclusion_criteria", sa.Text(), nullable=True),
        sa.Column("exclusion_criteria", sa.Text(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="created"),
        sa.Column("total_studies", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("owner_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"],
                                name="fk_reviews_owner_id_users"),
    )

    # ── studies ───────────────────────────────────────────────────────────────
    op.create_table(
        "studies",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("pmid", sa.String(20), nullable=True),
        sa.Column("pmcid", sa.String(20), nullable=True),
        sa.Column("doi", sa.String(256), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("authors", sa.Text(), nullable=True),
        sa.Column("journal", sa.String(512), nullable=True),
        sa.Column("publication_date", sa.String(20), nullable=True),
        sa.Column("mesh_terms", sa.Text(), nullable=True),
        sa.Column("pdf_path", sa.String(1024), nullable=True),
        sa.Column("pdf_available", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("full_text", sa.Text(), nullable=True),
        sa.Column("screening_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("extraction_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("validation_status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("review_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"],
                                name="fk_studies_review_id_reviews"),
    )
    op.create_index("ix_studies_pmid", "studies", ["pmid"])

    # ── task_logs ─────────────────────────────────────────────────────────────
    op.create_table(
        "task_logs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("review_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("celery_task_id", sa.String(256), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["review_id"], ["reviews.id"],
                                name="fk_task_logs_review_id_reviews"),
    )
    op.create_index("ix_task_logs_review_id", "task_logs", ["review_id"])

    # ── screenings ────────────────────────────────────────────────────────────
    op.create_table(
        "screenings",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("study_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["studies.id"],
                                name="fk_screenings_study_id_studies"),
    )
    op.create_index("ix_screenings_study_id", "screenings", ["study_id"])

    # ── extractions ───────────────────────────────────────────────────────────
    op.create_table(
        "extractions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("study_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("population", sa.Text(), nullable=True, server_default="Not Reported"),
        sa.Column("intervention", sa.Text(), nullable=True, server_default="Not Reported"),
        sa.Column("comparator", sa.Text(), nullable=True, server_default="Not Reported"),
        sa.Column("outcome", sa.Text(), nullable=True, server_default="Not Reported"),
        sa.Column("study_design", sa.Text(), nullable=True, server_default="Not Reported"),
        sa.Column("sample_size", sa.String(100), nullable=True, server_default="Not Reported"),
        sa.Column("duration", sa.String(256), nullable=True, server_default="Not Reported"),
        sa.Column("setting", sa.Text(), nullable=True, server_default="Not Reported"),
        sa.Column("confidence_scores", postgresql.JSONB(), nullable=True),
        sa.Column("source_quotes", postgresql.JSONB(), nullable=True),
        sa.Column("model_used", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["study_id"], ["studies.id"],
                                name="fk_extractions_study_id_studies"),
    )
    op.create_index("ix_extractions_study_id", "extractions", ["study_id"])

    # ── validations ───────────────────────────────────────────────────────────
    op.create_table(
        "validations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("extraction_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("validator_model", sa.String(100), nullable=False),
        sa.Column("validator_provider", sa.String(50), nullable=False),
        sa.Column("agreement_score", sa.Float(), nullable=False),
        sa.Column("field_agreements", postgresql.JSONB(), nullable=True),
        sa.Column("discrepancies", postgresql.JSONB(), nullable=True),
        sa.Column("validator_extractions", postgresql.JSONB(), nullable=True),
        sa.Column("needs_human_review", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("human_reviewed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("final_decision", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["extraction_id"], ["extractions.id"],
                                name="fk_validations_extraction_id_extractions"),
    )
    op.create_index("ix_validations_extraction_id", "validations", ["extraction_id"])

    # ── embeddings (pgvector) ─────────────────────────────────────────────────
    # Uses vector(768) for nomic-embed-text.
    # Includes all 8 metadata columns Vaibhav added in his RAG pipeline.
    op.execute("""
        CREATE TABLE embeddings (
            id          UUID PRIMARY KEY,
            study_id    UUID NOT NULL REFERENCES studies(id) ON DELETE CASCADE,
            chunk_text  TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            embedding   vector(768) NOT NULL,

            -- Vaibhav's retrieval metadata (8 new columns)
            document_id      VARCHAR(64),
            source_file_name VARCHAR(512),
            page_number      INTEGER,
            page_range       VARCHAR(100),
            chunk_id         VARCHAR(64) UNIQUE,
            section_hint     VARCHAR(512),
            has_table_content BOOLEAN NOT NULL DEFAULT false,
            char_count       INTEGER NOT NULL DEFAULT 0,

            created_at  TIMESTAMPTZ NOT NULL,
            updated_at  TIMESTAMPTZ NOT NULL
        )
    """)
    op.execute("CREATE INDEX ix_embeddings_study_id   ON embeddings (study_id)")
    op.execute("CREATE INDEX ix_embeddings_document_id ON embeddings (document_id)")
    op.execute("CREATE INDEX ix_embeddings_chunk_id    ON embeddings (chunk_id)")
    # HNSW index for fast cosine similarity search
    op.execute("""
        CREATE INDEX ix_embeddings_hnsw
        ON embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS embeddings CASCADE")
    op.drop_table("validations")
    op.drop_table("extractions")
    op.drop_table("screenings")
    op.drop_table("task_logs")
    op.drop_table("studies")
    op.drop_table("reviews")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
