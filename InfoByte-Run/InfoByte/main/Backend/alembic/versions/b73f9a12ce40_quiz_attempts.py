"""Persist quiz attempts and their question snapshots.

Revision ID: b73f9a12ce40
Revises: ae6923cd1f45
Create Date: 2026-11-19
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b73f9a12ce40"
down_revision: Union[str, None] = "ae6923cd1f45"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("test_id", sa.Integer(), nullable=False),
        sa.Column("test_title", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="in_progress", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("retry_of_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.CheckConstraint("question_count > 0", name="ck_quiz_attempts_question_count_positive"),
        sa.CheckConstraint(
            "status IN ('in_progress', 'completed')", name="ck_quiz_attempts_status_valid"
        ),
        sa.CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= question_count)",
            name="ck_quiz_attempts_score_range",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retry_of_id"], ["quiz_attempts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quiz_attempts_owner_id", "quiz_attempts", ["owner_id"])
    op.create_index("ix_quiz_attempts_retry_of_id", "quiz_attempts", ["retry_of_id"])

    op.create_table(
        "quiz_attempt_answers",
        sa.Column("attempt_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question_id", sa.Integer(), nullable=False),
        sa.Column("topic", sa.String(length=180), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("level", sa.String(length=80), nullable=False),
        sa.Column("selected_option", sa.Integer(), nullable=True),
        sa.Column("correct_option", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("reviewed", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_quiz_attempt_answers_position_nonnegative"),
        sa.CheckConstraint(
            "selected_option IS NULL OR selected_option >= 0",
            name="ck_quiz_attempt_answers_selected_nonnegative",
        ),
        sa.CheckConstraint("correct_option >= 0", name="ck_quiz_attempt_answers_correct_nonnegative"),
        sa.ForeignKeyConstraint(["attempt_id"], ["quiz_attempts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("attempt_id", "position"),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_quiz_attempt_answers_question"),
    )
    op.create_index(
        "ix_quiz_attempt_answers_question_id", "quiz_attempt_answers", ["question_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_quiz_attempt_answers_question_id", table_name="quiz_attempt_answers")
    op.drop_table("quiz_attempt_answers")
    op.drop_index("ix_quiz_attempts_retry_of_id", table_name="quiz_attempts")
    op.drop_index("ix_quiz_attempts_owner_id", table_name="quiz_attempts")
    op.drop_table("quiz_attempts")
