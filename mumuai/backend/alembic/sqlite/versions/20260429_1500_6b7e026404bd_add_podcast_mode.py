"""add podcast mode

Revision ID: 6b7e026404bd
Revises: d887fd1a30a6
Create Date: 2026-04-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b7e026404bd'
down_revision: Union[str, None] = 'd887fd1a30a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Project 表新增 content_mode
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('content_mode', sa.String(20), server_default=sa.text("'novel'"), nullable=False))

    # 2. Character 表新增音色字段
    with op.batch_alter_table('characters', schema=None) as batch_op:
        batch_op.add_column(sa.Column('voice_id', sa.String(100)))
        batch_op.add_column(sa.Column('voice_speed', sa.Float, server_default=sa.text("'1.0'")))
        batch_op.add_column(sa.Column('voice_pitch', sa.Float, server_default=sa.text("'0.0'")))
        batch_op.add_column(sa.Column('voice_sample', sa.String(500)))
        batch_op.add_column(sa.Column('catchphrase', sa.String(200)))

    # 3. AudioTask 表
    op.create_table('audio_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('chapter_id', sa.String(36), sa.ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(20), server_default=sa.text("'queued'")),
        sa.Column('dialogue_json', sa.JSON),
        sa.Column('bgm_prompt', sa.Text),
        sa.Column('progress', sa.Float, server_default=sa.text("'0'")),
        sa.Column('error_message', sa.Text),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # 4. AudioFile 表
    op.create_table('audio_files',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('audio_tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chapter_id', sa.String(36), sa.ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_path', sa.String(500)),
        sa.Column('duration_seconds', sa.Integer),
        sa.Column('file_size_bytes', sa.Integer),
        sa.Column('format', sa.String(10), server_default=sa.text("'mp3'")),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('audio_files')
    op.drop_table('audio_tasks')

    with op.batch_alter_table('characters', schema=None) as batch_op:
        batch_op.drop_column('catchphrase')
        batch_op.drop_column('voice_sample')
        batch_op.drop_column('voice_pitch')
        batch_op.drop_column('voice_speed')
        batch_op.drop_column('voice_id')

    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('content_mode')
