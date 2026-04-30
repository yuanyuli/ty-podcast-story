"""seed podcast writing styles

Revision ID: 8c7d3f2a1e5b
Revises: 6b7e026404bd
Create Date: 2026-04-30
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


revision: str = '8c7d3f2a1e5b'
down_revision: Union[str, None] = '6b7e026404bd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    writing_styles_table = table(
        'writing_styles',
        column('user_id', sa.String),
        column('name', sa.String),
        column('style_type', sa.String),
        column('preset_id', sa.String),
        column('description', sa.Text),
        column('prompt_content', sa.Text),
        column('order_index', sa.Integer),
    )

    podcast_styles = [
        {
            "user_id": None,
            "name": "睡前故事风",
            "style_type": "preset",
            "preset_id": "podcast_bedtime",
            "description": "温和舒缓的睡前故事风格，适合儿童睡前收听，语速缓慢句子简短",
            "prompt_content": "语速温和、句子简短(单句不超过15字)、多用拟声词和重复句式、每集结尾用\"小朋友们，想知道后面发生了什么吗？闭上眼睛，我们明天继续...\"",
            "order_index": 10
        },
        {
            "user_id": None,
            "name": "历史广播剧风",
            "style_type": "preset",
            "preset_id": "podcast_drama",
            "description": "节奏明快的历史广播剧风格，角色性格鲜明，适合儿童冒险故事",
            "prompt_content": "对话节奏明快、角色性格鲜明、旁白有画面感、适当使用环境音描述、每集结尾设置悬念钩子",
            "order_index": 11
        },
    ]

    op.bulk_insert(writing_styles_table, podcast_styles)
    print(f"已插入 {len(podcast_styles)} 条播客写作风格预设")


def downgrade() -> None:
    op.execute("DELETE FROM writing_styles WHERE preset_id IN ('podcast_bedtime', 'podcast_drama')")
    print("已删除播客写作风格预设")
