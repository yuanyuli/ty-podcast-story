# 播客模式改造 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 MuMuAINovel 上新增播客内容模式（podcast mode），支持生成广播剧格式文本、多角色 TTS 语音、BGM 混音、MP3 导出。

**Architecture:** 数据库新增 content_mode + voice_* 字段 + AudioTask/AudioFile 表；后端新增 6 个播客 Prompt 模板 + audio_service 编排流水线；ComfyUI 宿主机暴露 8188 端口供 TTS 调用；前端新增 AudioStudio 页面 + AudioPlayer 组件。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy / Alembic / React 18 / TypeScript / Ant Design / FFmpeg

---

## 文件结构总览

### 新建文件
| 文件 | 职责 |
|------|------|
| `backend/app/models/audio_task.py` | AudioTask SQLAlchemy 模型 |
| `backend/app/models/audio_file.py` | AudioFile SQLAlchemy 模型 |
| `backend/app/schemas/audio.py` | 音频相关 Pydantic schemas |
| `backend/app/services/dialogue_parser.py` | 对话解析器（正则提取【角色名】格式） |
| `backend/app/services/tts_client.py` | ComfyUI VoxCPM HTTP 客户端 |
| `backend/app/services/bgm_client.py` | ACE-Step / 预置库 BGM 客户端 |
| `backend/app/services/mixer.py` | FFmpeg 混音模块 |
| `backend/app/services/audio_service.py` | 音频生成编排服务 |
| `backend/app/api/audio.py` | 音频 API 路由 |
| `frontend/src/pages/AudioStudio.tsx` | 音频工作室页面 |
| `frontend/src/components/AudioPlayer.tsx` | 音频播放器组件 |
| `frontend/src/components/AudioProgressModal.tsx` | 音频生成进度弹窗 |

### 修改文件
| 文件 | 变更 |
|------|------|
| `backend/app/models/project.py` | +content_mode 字段 |
| `backend/app/models/character.py` | +voice_id/speed/pitch/sample/catchphrase |
| `backend/app/models/__init__.py` | +导出新模型 |
| `backend/app/config.py` | +ComfyUI/ACE-Step/音频输出配置 |
| `backend/app/services/prompt_service.py` | +6 个播客模板常量 |
| `backend/app/schemas/project.py` | +content_mode 到 schemas |
| `backend/app/schemas/character.py` | +voice 字段到 schemas |
| `backend/app/api/chapters.py` | +播客模式生成分支 |
| `backend/app/api/outlines.py` | +播客大纲生成分支 |
| `backend/app/api/characters.py` | +音色参考音频上传端点 |
| `backend/app/api/wizard_stream.py` | +播客模式向导步骤 |
| `backend/app/main.py` | +注册 audio 路由 |
| `backend/requirements.txt` | +ffmpeg-python |
| `Dockerfile` | +安装 FFmpeg |
| `frontend/src/types/index.ts` | +AudioTask/AudioFile/VoiceConfig 类型 |
| `frontend/src/services/api.ts` | +audioApi 模块 |
| `frontend/src/pages/Chapters.tsx` | +生成播客按钮 |
| `frontend/src/App.tsx` | +AudioStudio 路由 |

---

## Phase 1: 数据库基础设施

### Task 1: 创建数据库迁移（PostgreSQL）

**Files:**
- Create: `backend/alembic/postgres/versions/20260429_XXXX_add_podcast_mode.py`

- [ ] **Step 1: 检查当前迁移 head**

```bash
cd /d/codebase/mu_ai_novel/mumuai/backend
grep -r "revision" alembic/postgres/versions/*.py | tail -1
```
记下最新的 revision ID（down_revision 需要用）。

- [ ] **Step 2: 编写迁移脚本**

```python
"""add podcast mode

Revision ID: podcast_001
Revises: <最新revision>
Create Date: 2026-04-29

"""
from alembic import op
import sqlalchemy as sa

revision = 'podcast_001'
down_revision = '<最新revision>'
branch_labels = None
depends_on = None

def upgrade():
    # 1. Project 表新增 content_mode
    op.add_column('projects',
        sa.Column('content_mode', sa.String(20), server_default='novel', nullable=False)
    )
    op.create_check_constraint(
        'check_content_mode', 'projects',
        "content_mode IN ('novel', 'podcast')"
    )

    # 2. Character 表新增音色字段
    op.add_column('characters', sa.Column('voice_id', sa.String(100)))
    op.add_column('characters', sa.Column('voice_speed', sa.Float, server_default='1.0'))
    op.add_column('characters', sa.Column('voice_pitch', sa.Float, server_default='0.0'))
    op.add_column('characters', sa.Column('voice_sample', sa.String(500)))
    op.add_column('characters', sa.Column('catchphrase', sa.String(200)))

    # 3. AudioTask 表
    op.create_table('audio_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('chapter_id', sa.String(36), sa.ForeignKey('chapters.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(20), server_default='queued'),
        sa.Column('dialogue_json', sa.JSON),
        sa.Column('bgm_prompt', sa.Text),
        sa.Column('progress', sa.Float, server_default='0'),
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
        sa.Column('format', sa.String(10), server_default='mp3'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table('audio_files')
    op.drop_table('audio_tasks')
    op.drop_column('characters', 'catchphrase')
    op.drop_column('characters', 'voice_sample')
    op.drop_column('characters', 'voice_pitch')
    op.drop_column('characters', 'voice_speed')
    op.drop_column('characters', 'voice_id')
    op.execute('ALTER TABLE projects DROP CONSTRAINT IF EXISTS check_content_mode')
    op.drop_column('projects', 'content_mode')
```

- [ ] **Step 3: 创建 SQLite 对应迁移**

在 `backend/alembic/sqlite/versions/` 下创建同名迁移，移除 PostgreSQL 特有语法（check constraint 用简单写法）。

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/
git commit -m "feat: add podcast mode database migrations (content_mode, voice fields, audio_tasks, audio_files)"
```

---

### Task 2: 更新 SQLAlchemy 模型

**Files:**
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/models/character.py`
- Create: `backend/app/models/audio_task.py`
- Create: `backend/app/models/audio_file.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: 更新 Project 模型**

在 `project.py` 添加：

```python
content_mode = Column(String(20), default="novel", nullable=False)
```

- [ ] **Step 2: 更新 Character 模型**

在 `character.py` 添加：

```python
voice_id = Column(String(100), nullable=True)
voice_speed = Column(Float, default=1.0)
voice_pitch = Column(Float, default=0.0)
voice_sample = Column(String(500), nullable=True)
catchphrase = Column(String(200), nullable=True)
```

- [ ] **Step 3: 创建 AudioTask 模型**

`audio_task.py`:

```python
from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class AudioTask(Base):
    __tablename__ = "audio_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="queued")  # queued/parsing/tts/bgm/mixing/done/failed
    dialogue_json = Column(JSON, nullable=True)
    bgm_prompt = Column(Text, nullable=True)
    progress = Column(Float, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    chapter = relationship("Chapter", backref="audio_tasks")
    project = relationship("Project", backref="audio_tasks")
```

- [ ] **Step 4: 创建 AudioFile 模型**

`audio_file.py`:

```python
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid

class AudioFile(Base):
    __tablename__ = "audio_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("audio_tasks.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(500), nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    format = Column(String(10), default="mp3")
    created_at = Column(DateTime, server_default=func.now())

    task = relationship("AudioTask", backref="audio_files")
    chapter = relationship("Chapter", backref="audio_files")
    project = relationship("Project", backref="audio_files")
```

- [ ] **Step 5: 更新 __init__.py**

```python
from app.models.audio_task import AudioTask
from app.models.audio_file import AudioFile
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add AudioTask and AudioFile models, update Project/Character with podcast fields"
```

---

### Task 3: 更新 Pydantic Schemas

**Files:**
- Modify: `backend/app/schemas/project.py`
- Modify: `backend/app/schemas/character.py`
- Create: `backend/app/schemas/audio.py`

- [ ] **Step 1: 更新 Project schemas**

在 `project.py` 的 `ProjectCreate`, `ProjectUpdate`, `ProjectResponse` 中添加：

```python
content_mode: Optional[str] = "novel"
```

- [ ] **Step 2: 更新 Character schemas**

在 `character.py` 的 `CharacterCreate`, `CharacterUpdate`, `CharacterResponse` 中添加：

```python
voice_id: Optional[str] = None
voice_speed: Optional[float] = 1.0
voice_pitch: Optional[float] = 0.0
voice_sample: Optional[str] = None
catchphrase: Optional[str] = None
```

- [ ] **Step 3: 创建 Audio schemas**

`audio.py`:

```python
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class DialogueSegment(BaseModel):
    order: int
    speaker: str
    text: str
    emotion: Optional[str] = "neutral"
    estimated_duration_ms: Optional[int] = 0

class AudioGenerateRequest(BaseModel):
    bgm_style: Optional[str] = None
    voice_overrides: Optional[dict] = None

class AudioTaskResponse(BaseModel):
    id: str
    chapter_id: str
    status: str
    progress: float
    error_message: Optional[str] = None
    created_at: datetime

class AudioFileResponse(BaseModel):
    id: str
    chapter_id: str
    file_path: str
    duration_seconds: int
    file_size_bytes: int
    format: str
    created_at: datetime

class BGMPreset(BaseModel):
    id: str
    name: str
    style: str
    tags: List[str]
    path: Optional[str] = None

class VoiceSampleUploadResponse(BaseModel):
    voice_sample: str
    message: str
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat: update schemas for podcast mode (project, character, audio)"
```

---

### Task 4: 更新应用配置

**Files:**
- Modify: `backend/app/config.py`

- [ ] **Step 1: 添加播客相关配置项**

在 `Settings` 类中添加：

```python
# ComfyUI
comfyui_base_url: str = "http://host.docker.internal:8188"
comfyui_timeout: int = 300

# ACE-Step (optional)
acestep_api_url: Optional[str] = None
acestep_timeout: int = 120

# Audio output
audio_output_dir: str = "/app/data/audio"
audio_format: str = "mp3"
audio_bitrate: str = "128k"

# BGM presets directory (relative to audio_output_dir)
bgm_presets_dir: str = "bgm_presets"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/config.py
git commit -m "feat: add ComfyUI/ACE-Step/audio config to Settings"
```

---

## Phase 2: 播客内容模式

### Task 5: 添加播客 Prompt 模板

**Files:**
- Modify: `backend/app/services/prompt_service.py`

- [ ] **Step 1: 在 PromptService 类中添加 6 个模板常量**

位置：在现有 `CHAPTER_GENERATION_ONE_TO_ONE_NEXT` 之后，类体内部。

```python
PODCAST_WORLD = """<system>
你是一位专业的儿童广播剧世界观设计师，擅长为3-10岁小朋友打造沉浸式历史穿越故事的世界设定...
</system>

<task>
根据以下项目信息，设计一个适合儿童睡前广播剧的世界观设定，包括时代背景、声音氛围、BGM风格建议。
项目名称：{project_title}
目标年龄段：{target_age}
历史时期：{historical_period}
</task>

<requirements>
1. 时代背景描述要生动有趣，让小朋友一听就有画面感
2. 声音氛围要具体：比如清晨的鸟叫、集市的喧闹、远处的马蹄声
3. 提供 BGM 风格建议：情绪、乐器、节奏
</requirements>

<output>
请输出 JSON 格式：
{{"time_period": "朝代+具体时期", "location": "主要场景地点", "audio_atmosphere": "声音氛围描述（3-5句）", "bgm_style": "乐器+节奏+情绪", "sound_effects": ["场景音效1", "场景音效2"]}}
</output>"""

PODCAST_OUTLINE = """<system>
你是儿童广播剧的编剧，擅长将历史故事改编为有趣的穿越冒险剧集...
</system>

<task>
为《{project_title}》设计剧集大纲。每集5-8分钟，用"小朋友穿越到历史现场"的方式讲故事。
主角：{main_characters}
历史时期：{historical_period}
</task>

<requirements>
1. 每集必须有一个清晰的历史知识点
2. 必须有一个穿越的趣味场景（比如掉进古代厨房/集市/战场）
3. 必须有一个角色互动亮点（和历史人物的对话）
4. 结尾必须有悬念钩子
5. 预估时长5-8分钟（约1500-2500字）
</requirements>

<output>
按以下 JSON 格式输出剧集列表：
[{{"episode_number": 1, "title": "...", "historical_period": "...", "historical_figure": "...", "knowledge_point": "...", "character_focus": "...", "emotion": "...", "cliffhanger": "...", "bgm_style": "...", "estimated_duration": "6分钟"}}]
</output>"""

PODCAST_EPISODE_FIRST = """<system>
你是儿童广播剧的剧本作家，使用"旁白叙述+角色对话"的广播剧格式创作内容。你的作品将在喜马拉雅等平台播放，听众是3-10岁的小朋友和他们的家长。
</system>

<task>
请创作《{project_title}》的第{episode_number}集：{episode_title}。
这是该系列的第一集，需要建立世界观、介绍主角团、展开第一次穿越冒险。
</task>

<input>
历史时期：{historical_period}
历史人物：{historical_figure}
知识点：{knowledge_point}
角色聚焦：{character_focus}
情感基调：{emotion}
目标字数：{target_word_count}字（对应{estimated_duration}时长）

主角团：
{characters_info}

场景描述：
{scenes}
</input>

<guidelines>
1. 必须使用【角色名】格式标注每一段发言，包括【旁白】
2. 对话要生动有趣，每个角色都有鲜明的说话风格
3. 冯奇奇：好奇捣蛋，总问"为什么"
4. 五花：三句不离吃的，但关键时刻很靠谱
5. 布皮冻：说话像果冻一样Q弹，喜欢说"你猜怎么着"
6. 白木苏：温和有耐心，像讲故事的大哥哥
7. 肥笼：用"喵呜"和动作参与剧情
8. 历史人物说话要符合身份但有反差萌
9. 旁白语言要温暖有画面感，像睡前故事
10. 结尾设置悬念："小朋友们，姜子牙的鱼钩上为什么没有鱼饵呢？闭上眼睛想一想，我们明天见~"
</guidelines>

<constraints>
- 总字数控制在{target_word_count}字以内
- 每段对话不超过50字（小朋友注意力）
- 必须有至少2个角色之间的互动对话
- 必须有一个让小朋友笑出声的桥段
</constraints>

<output>
请直接按以下格式输出广播剧内容：

【旁白】（历史场景描述，温暖有画面感）
【角色名1】（对话内容，动作描述用括号）
【角色名2】（对话内容）
【旁白】（转场叙述）
...
</output>"""

PODCAST_EPISODE_NEXT = PODCAST_EPISODE_FIRST.replace(
    "这是该系列的第一集，需要建立世界观、介绍主角团、展开第一次穿越冒险。",
    "这是第{episode_number}集，需要承接上一集的悬念（{prev_cliffhanger}），继续展开冒险。"
)

PODCAST_CHARACTER = """<system>
你是儿童广播剧的角色设计师，擅长为有声故事设计声音辨识度极高的角色。
</system>

<task>
为广播剧《{project_title}》设计角色的详细设定，特别注重声音特征和口头禅。
</task>

<output>
请输出 JSON 格式：
{{"name": "...", "age": "...", "gender": "...", "personality": "...", "voice_style": "清脆/稚嫩/低沉/欢快等", "speaking_pattern": "说话节奏和习惯", "catchphrase": "口头禅"}}
</output>"""

PODCAST_REGENERATE = PODCAST_EPISODE_FIRST.replace(
    "请创作", "根据以下反馈重新创作"
)
```

- [ ] **Step 2: 在 get_all_system_templates() 中注册**

在 `template_definitions` 字典中添加：

```python
"PODCAST_WORLD": {
    "name": "播客世界观",
    "category": "世界构建",
    "description": "设计儿童广播剧的世界观设定和声音氛围",
    "parameters": ["project_title", "target_age", "historical_period"]
},
"PODCAST_OUTLINE": {
    "name": "播客剧集大纲",
    "category": "大纲生成",
    "description": "将历史故事改编为广播剧剧集大纲",
    "parameters": ["project_title", "main_characters", "historical_period"]
},
"PODCAST_EPISODE_FIRST": {
    "name": "播客第1集",
    "category": "章节创作",
    "description": "生成广播剧第1集完整内容（含开场和角色引入）",
    "parameters": ["project_title", "episode_number", "episode_title", "historical_period", "historical_figure", "knowledge_point", "character_focus", "emotion", "target_word_count", "estimated_duration", "characters_info", "scenes"]
},
"PODCAST_EPISODE_NEXT": {
    "name": "播客后续集",
    "category": "章节创作",
    "description": "生成广播剧后续集内容（承接上集悬念）",
    "parameters": ["project_title", "episode_number", "episode_title", "historical_period", "historical_figure", "knowledge_point", "character_focus", "emotion", "target_word_count", "estimated_duration", "characters_info", "scenes", "prev_cliffhanger"]
},
"PODCAST_CHARACTER": {
    "name": "播客角色",
    "category": "角色生成",
    "description": "设计广播剧角色（侧重声音特征）",
    "parameters": ["project_title"]
},
"PODCAST_REGENERATE": {
    "name": "播客重生成",
    "category": "章节重写",
    "description": "根据反馈重新生成广播剧内容",
    "parameters": ["project_title", "episode_number", "episode_title", "feedback", "characters_info"]
}
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/prompt_service.py
git commit -m "feat: add 6 podcast prompt templates (WORLD, OUTLINE, EPISODE_FIRST, EPISODE_NEXT, CHARACTER, REGENERATE)"
```

---

### Task 6: 播客大纲模式

**Files:**
- Modify: `backend/app/api/outlines.py`
- Modify: `backend/app/schemas/outline.py`

- [ ] **Step 1: 更新 Outline schema**

在 `outline.py` 中添加 `PodcastOutlineStructure`：

```python
class PodcastOutlineStructure(BaseModel):
    episode_number: int
    title: str
    historical_period: Optional[str] = None
    historical_figure: Optional[str] = None
    knowledge_point: Optional[str] = None
    character_focus: Optional[str] = None
    scenes: Optional[List[str]] = None
    emotion: Optional[str] = None
    cliffhanger: Optional[str] = None
    bgm_style: Optional[str] = None
    estimated_duration: Optional[str] = None
```

- [ ] **Step 2: 在 outlines.py 添加播客大纲生成**

在 `generate_outline_stream` 端点中（约第700行附近），在模板选择逻辑中添加：

```python
if project.content_mode == 'podcast':
    template = await PromptService.get_template(
        "PODCAST_OUTLINE", current_user_id, db
    )
    base_prompt = PromptService.format_prompt(
        template,
        project_title=project.title,
        main_characters="冯奇奇、五花、布皮冻、白木苏、肥笼",
        historical_period=project.world_time_period or "商朝末年"
    )
    # 使用非流式 generate_text + JSON 解析
    result = await user_ai_service.generate_text(
        prompt=base_prompt,
        max_tokens=4000,
    )
    # 解析 JSON → 创建 Outline 行
    outlines_data = json.loads(...)
    for item in outlines_data:
        outline = Outline(
            project_id=project_id,
            title=item["title"],
            structure=json.dumps(item),
            order_index=item["episode_number"]
        )
        db.add(outline)
    await db.commit()
    yield f"data: {json.dumps({'done': True, 'count': len(outlines_data)})}\n\n"
    return
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/outlines.py backend/app/schemas/outline.py
git commit -m "feat: add podcast outline generation mode"
```

---

### Task 7: 对话解析器

**Files:**
- Create: `backend/app/services/dialogue_parser.py`

- [ ] **Step 1: 创建 dialogue_parser.py**

```python
"""对话解析器：从广播剧文本中提取结构化对话段"""
import re
from typing import List, Dict, Any

def parse_dialogue(text: str) -> List[Dict[str, Any]]:
    """
    解析【角色名】格式的广播剧文本，返回 dialogue_json 结构。

    Args:
        text: 包含【角色名】标注的广播剧文本

    Returns:
        [{"order": 1, "speaker": "旁白", "text": "...", "emotion": "neutral", "estimated_duration_ms": 0}, ...]
    """
    pattern = r'【(.+?)】(.+?)(?=【|$)'
    matches = re.findall(pattern, text, re.DOTALL)

    if not matches:
        return []

    segments = []
    for i, (speaker, content) in enumerate(matches):
        content = content.strip()
        # 估算时长：中文约 4字/秒
        estimated_ms = len(content) * 250

        segments.append({
            "order": i + 1,
            "speaker": speaker.strip(),
            "text": content,
            "emotion": "neutral",
            "estimated_duration_ms": estimated_ms
        })

    return segments


def validate_podcast_format(text: str) -> Dict[str, Any]:
    """
    验证广播剧文本是否符合格式要求。

    Returns:
        {"valid": bool, "errors": [], "warnings": [], "stats": {}}
    """
    result = {"valid": True, "errors": [], "warnings": [], "stats": {}}

    # 检查是否有【旁白】标签
    if "【旁白】" not in text:
        result["errors"].append("缺少【旁白】标签")
        result["valid"] = False

    # 检查角色标签
    segments = parse_dialogue(text)
    speakers = set(s["speaker"] for s in segments)
    result["stats"]["speakers"] = list(speakers)
    result["stats"]["segment_count"] = len(segments)

    # 字数检查（1500-2500 为目标）
    total_chars = len(text.replace('\n', '').replace(' ', ''))
    result["stats"]["total_chars"] = total_chars
    if total_chars < 1000:
        result["warnings"].append(f"字数偏少({total_chars}), 建议1500-2500字")
    elif total_chars > 3000:
        result["warnings"].append(f"字数偏多({total_chars}), 可能超过8分钟")

    # 检查对话是否过长
    for seg in segments:
        if len(seg["text"]) > 100:
            result["warnings"].append(
                f"第{seg['order']}段({seg['speaker']})对话过长({len(seg['text'])}字)"
            )

    return result
```

- [ ] **Step 2: 编写测试**

在 `backend/tests/` 下创建 `test_dialogue_parser.py`：

```python
def test_parse_dialogue():
    text = "【旁白】商朝末年，朝歌城外...\n【冯奇奇】（揉揉眼睛）咦？这是哪儿？\n【旁白】远处，一个白发老者走来..."
    result = parse_dialogue(text)
    assert len(result) == 3
    assert result[0]["speaker"] == "旁白"
    assert result[1]["speaker"] == "冯奇奇"
    assert result[1]["text"].startswith("（揉揉眼睛）")

def test_empty_text():
    assert parse_dialogue("") == []

def test_validate_podcast_format():
    valid_text = "【旁白】故事开始...【冯奇奇】你好！【旁白】结束了。"
    result = validate_podcast_format(valid_text)
    assert result["valid"] is True
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/dialogue_parser.py backend/tests/test_dialogue_parser.py
git commit -m "feat: add dialogue parser for podcast 【角色名】format"
```

---

### Task 8: 播客章节生成（chapters.py 分支）

**Files:**
- Modify: `backend/app/api/chapters.py`

- [ ] **Step 1: 在 generate_chapter_content_stream 中添加播客分支**

在模板选择区域（约行1518），添加：

```python
if project.content_mode == 'podcast':
    # 确定是第一集还是后续集
    is_first = not has_previous_chapters(project_id, current_chapter.chapter_number, db)

    template_key = "PODCAST_EPISODE_FIRST" if is_first else "PODCAST_EPISODE_NEXT"
    template = await PromptService.get_template(template_key, current_user_id, db_session)

    # 从 outline.structure 提取播客大纲数据
    outline_data = json.loads(current_outline.structure) if current_outline and current_outline.structure else {}

    base_prompt = PromptService.format_prompt(
        template,
        project_title=project.title,
        episode_number=current_chapter.chapter_number,
        episode_title=current_chapter.title or outline_data.get("title", ""),
        historical_period=outline_data.get("historical_period", project.world_time_period or "商朝末年"),
        historical_figure=outline_data.get("historical_figure", ""),
        knowledge_point=outline_data.get("knowledge_point", ""),
        character_focus=outline_data.get("character_focus", ""),
        emotion=outline_data.get("emotion", "好奇"),
        target_word_count=str(target_word_count),
        estimated_duration=outline_data.get("estimated_duration", "6分钟"),
        characters_info=characters_info,  # 复用现有角色格式化逻辑
        scenes="\n".join(outline_data.get("scenes", [])),
        prev_cliffhanger="" if is_first else previous_outline.get("cliffhanger", ""),
    )
```

- [ ] **Step 2: 生成后自动解析对话**

在保存章节内容后，自动验证格式：

```python
# 保存章节内容
current_chapter.content = full_content
current_chapter.status = "completed"
current_chapter.word_count = len(full_content)

# 播客模式：自动解析并验证
if project.content_mode == 'podcast':
    from app.services.dialogue_parser import validate_podcast_format
    validation = validate_podcast_format(full_content)
    if not validation["valid"]:
        yield f"data: {json.dumps({'type': 'warning', 'message': '格式验证失败: ' + '; '.join(validation['errors'])})}\n\n"
    if validation["warnings"]:
        yield f"data: {json.dumps({'type': 'warning', 'message': '; '.join(validation['warnings'])})}\n\n"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/chapters.py
git commit -m "feat: add podcast episode generation branch in chapters.py"
```

---

### Task 9: 播客向导模式 + 角色音色上传

**Files:**
- Modify: `backend/app/api/wizard_stream.py`
- Modify: `backend/app/api/characters.py`

- [ ] **Step 1: wizard_stream.py 添加播客模式步骤**

在 `world_building_generator` 中根据 `content_mode` 分支：

```python
content_mode = data.get("content_mode", "novel")

if content_mode == 'podcast':
    template = await PromptService.get_template("PODCAST_WORLD", current_user_id, db)
    # 使用播客世界观模板
```

- [ ] **Step 2: characters.py 添加音色参考音频上传**

新增端点：

```python
@router.post("/{character_id}/voice-sample")
async def upload_voice_sample(
    character_id: str,
    file: UploadFile = File(...),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # 验证文件 < 5MB
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(400, "文件大小不能超过 5MB")

    # 保存为 WAV
    char_dir = Path(settings.audio_output_dir) / "voice_samples" / character_id
    char_dir.mkdir(parents=True, exist_ok=True)
    file_path = char_dir / "reference.wav"

    # 如果不是 WAV，用 FFmpeg 转码
    if not file.filename.endswith('.wav'):
        import subprocess
        subprocess.run(['ffmpeg', '-i', 'pipe:0', '-ar', '16000', '-ac', '1', str(file_path)],
                      input=content, capture_output=True)
    else:
        file_path.write_bytes(content)

    # 更新数据库
    char = await db.get(Character, character_id)
    char.voice_sample = str(file_path.relative_to(settings.audio_output_dir))
    await db.commit()

    return {"voice_sample": char.voice_sample, "message": "上传成功"}

@router.delete("/{character_id}/voice-sample")
async def delete_voice_sample(...):
    # 删除文件和清空字段
    ...
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/wizard_stream.py backend/app/api/characters.py
git commit -m "feat: add podcast wizard mode and voice sample upload API"
```

---

## Phase 3: TTS 集成

### Task 10: ComfyUI VoxCPM 客户端

**Files:**
- Create: `backend/app/services/tts_client.py`

- [ ] **Step 1: 创建 tts_client.py**

```python
"""ComfyUI VoxCPM TTS 客户端"""
import json
import time
import httpx
from pathlib import Path
from typing import Optional
from app.config import settings

class ComfyUITTSClient:
    def __init__(self):
        self.base_url = settings.comfyui_base_url.rstrip('/')
        self.timeout = settings.comfyui_timeout

    async def generate_speech(
        self,
        text: str,
        voice_sample_path: str,
        speed: float = 1.0,
        output_dir: str = "/app/data/audio/temp"
    ) -> str:
        """
        调用 ComfyUI VoxCPM 生成语音。

        Args:
            text: 要合成的文本
            voice_sample_path: 参考音频路径（zero-shot 音色克隆）
            speed: 语速
            output_dir: 输出目录

        Returns:
            生成的 WAV 文件路径
        """
        # 构建 VoxCPM workflow JSON
        workflow = self._build_workflow(text, voice_sample_path, speed)

        async with httpx.AsyncClient(timeout=30) as client:
            # 1. 提交 prompt
            resp = await client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow}
            )
            prompt_data = resp.json()
            prompt_id = prompt_data["prompt_id"]

            # 2. 轮询等待完成
            deadline = time.time() + self.timeout
            while time.time() < deadline:
                history_resp = await client.get(
                    f"{self.base_url}/history/{prompt_id}"
                )
                history = history_resp.json()

                if prompt_id in history:
                    # 提取输出文件路径
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, node_output in outputs.items():
                        for filename in node_output.get("audio", []):
                            return str(Path(output_dir) / filename)

                await asyncio.sleep(1)

            raise TimeoutError(f"TTS generation timed out after {self.timeout}s")

    def _build_workflow(self, text: str, reference_audio: str, speed: float) -> dict:
        """构建 ComfyUI VoxCPM workflow"""
        # Workflow 结构依赖 VoxCPM 具体节点，实现时根据实际节点调整
        return {
            "3": {
                "class_type": "VoxCPM_TTS",
                "inputs": {
                    "text": text,
                    "reference_audio": reference_audio,
                    "speed": speed,
                    "seed": int(time.time())
                }
            },
            "4": {
                "class_type": "SaveAudio",
                "inputs": {
                    "filename_prefix": "tts_output",
                    "audio": ["3", 0]
                }
            }
        }

tts_client = ComfyUITTSClient()
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/tts_client.py
git commit -m "feat: add ComfyUI VoxCPM TTS client"
```

---

### Task 11: BGM 客户端 + 混音模块

**Files:**
- Create: `backend/app/services/bgm_client.py`
- Create: `backend/app/services/mixer.py`

- [ ] **Step 1: 创建 bgm_client.py**

```python
"""BGM 音乐生成客户端：ACE-Step + 预置库兜底"""
import json
import httpx
import random
from pathlib import Path
from typing import Optional
from app.config import settings

class BGMClient:
    def __init__(self):
        self.acestep_url = settings.acestep_api_url
        self.presets: list[dict] = []

    async def get_bgm(self, style: str, output_path: str) -> str:
        """获取背景音乐，按需生成或从预置库匹配"""
        if self.acestep_url:
            try:
                return await self._generate_acestep(style, output_path)
            except Exception:
                pass  # fallback to presets

        return self._match_preset(style)

    async def _generate_acestep(self, style: str, output_path: str) -> str:
        """调用 ACE-Step API 生成 BGM"""
        async with httpx.AsyncClient(timeout=settings.acestep_timeout) as client:
            resp = await client.post(
                f"{self.acestep_url}/generate",
                json={"prompt": f"instrumental background music, {style}, gentle, children's story"}
            )
            data = resp.json()
            # 下载音频文件
            audio_url = data.get("audio_url")
            if audio_url:
                audio_resp = await client.get(audio_url)
                Path(output_path).write_bytes(audio_resp.content)
                return output_path
            raise Exception("ACE-Step returned no audio")

    def _match_preset(self, style: str) -> str:
        """从预置 BGM 库匹配最合适的音乐"""
        if not self.presets:
            self._load_presets()

        # 简单标签匹配
        style_lower = style.lower()
        matches = [p for p in self.presets
                   if any(tag in style_lower for tag in p.get("tags", []))]

        if matches:
            return random.choice(matches)["path"]

        # 无匹配时返回默认 BGM
        return random.choice(self.presets)["path"] if self.presets else ""

    def _load_presets(self):
        """加载预置 BGM 列表"""
        presets_file = Path(settings.audio_output_dir) / "bgm_presets" / "index.json"
        if presets_file.exists():
            self.presets = json.loads(presets_file.read_text())
        else:
            # 内置默认预设
            self.presets = [
                {"id": "calm_morning", "name": "宁静清晨", "tags": ["calm", "morning", "gentle"], "path": ""},
                {"id": "ancient_city", "name": "古城漫步", "tags": ["ancient", "city", "adventure"], "path": ""},
                {"id": "mystery_forest", "name": "神秘森林", "tags": ["mystery", "nature", "wonder"], "path": ""},
                {"id": "happy_ending", "name": "快乐结尾", "tags": ["happy", "warm", "ending"], "path": ""},
            ]

bgm_client = BGMClient()
```

- [ ] **Step 2: 创建 mixer.py**

```python
"""FFmpeg 混音模块"""
import subprocess
import asyncio
from pathlib import Path
from typing import List

class AudioMixer:
    async def mix(
        self,
        tts_segments: List[dict],  # [{"path": "...", "order": 1, "speaker": "..."}, ...]
        bgm_path: str,
        output_path: str,
        bgm_volume: float = 0.15,
        fade_in: float = 2.0,
        fade_out: float = 3.0,
    ) -> str:
        """
        将多段 TTS 语音和 BGM 混音为最终 MP3。

        Args:
            tts_segments: TTS 片段列表（按 order 排序）
            bgm_path: 背景音乐文件路径
            output_path: 输出 MP3 路径
            bgm_volume: BGM 音量比例 (0-1)
            fade_in: 淡入秒数
            fade_out: 淡出秒数
        """
        # 确保输出目录存在
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 按 order 排序
        tts_segments.sort(key=lambda s: s["order"])

        # 1. 拼接所有 TTS 片段
        concat_file = Path(output_path).parent / "concat_list.txt"
        concat_content = "\n".join(
            f"file '{seg['path']}'" for seg in tts_segments
        )
        concat_file.write_text(concat_content)

        speech_output = Path(output_path).parent / "speech_combined.wav"
        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(speech_output)
        ]
        await self._run_ffmpeg(cmd_concat)

        # 2. 混音：语音 + BGM
        cmd_mix = [
            "ffmpeg", "-y",
            "-i", str(speech_output),
            "-i", bgm_path,
            "-filter_complex",
            f"[1:a]volume={bgm_volume},afade=t=in:d={fade_in},afade=t=out:d={fade_out}[bgm];"
            f"[0:a][bgm]amix=inputs=2:duration=first[out]",
            "-map", "[out]",
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            str(output_path)
        ]
        await self._run_ffmpeg(cmd_mix)

        # 清理临时文件
        concat_file.unlink(missing_ok=True)
        speech_output.unlink(missing_ok=True)

        return output_path

    async def _run_ffmpeg(self, cmd: List[str]):
        """运行 FFmpeg 命令"""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")

mixer = AudioMixer()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/bgm_client.py backend/app/services/mixer.py
git commit -m "feat: add BGM client (ACE-Step + presets) and FFmpeg mixer"
```

---

### Task 12: 音频生成编排服务 + API 路由

**Files:**
- Create: `backend/app/services/audio_service.py`
- Create: `backend/app/api/audio.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 创建 audio_service.py**

```python
"""音频生成编排服务"""
import json
import asyncio
from pathlib import Path
from typing import AsyncGenerator
from app.config import settings
from app.services.dialogue_parser import parse_dialogue
from app.services.tts_client import tts_client
from app.services.bgm_client import bgm_client
from app.services.mixer import mixer

class AudioGenerationService:
    async def generate_audio_stream(
        self,
        chapter_id: str,
        chapter_content: str,
        bgm_style: str = "ancient children adventure"
    ) -> AsyncGenerator[str, None]:
        """SSE 流式推送音频生成进度"""

        output_dir = Path(settings.audio_output_dir) / "temp" / chapter_id
        output_dir.mkdir(parents=True, exist_ok=True)

        # Step 1: 对话解析
        yield self._sse_event("progress", {"step": "parsing", "progress": 5, "message": "正在解析对话..."})
        segments = parse_dialogue(chapter_content)
        if not segments:
            yield self._sse_event("error", {"message": "未检测到【角色名】格式对话"})
            return

        yield self._sse_event("progress", {"step": "parsing", "progress": 10,
                            "message": f"解析完成：{len(set(s['speaker'] for s in segments))}个角色，{len(segments)}段对话"})

        # Step 2: 多角色 TTS
        yield self._sse_event("progress", {"step": "tts", "progress": 15, "message": "开始生成语音..."})

        unique_speakers = list(set(s["speaker"] for s in segments))
        speaker_voice_map = await self._get_voice_map(unique_speakers)

        tts_segments = []
        total = len(segments)
        for i, seg in enumerate(segments):
            progress = 15 + int(50 * i / total)  # 15% → 65%
            yield self._sse_event("progress", {
                "step": "tts", "progress": progress,
                "message": f"生成 {seg['speaker']} 语音 ({i+1}/{total})..."
            })

            voice_sample = speaker_voice_map.get(seg["speaker"], "")
            seg_path = output_dir / f"{i+1:03d}_{seg['speaker']}.wav"
            await tts_client.generate_speech(
                text=seg["text"],
                voice_sample_path=voice_sample,
                output_dir=str(output_dir)
            )
            tts_segments.append({"path": str(seg_path), "order": seg["order"], "speaker": seg["speaker"]})

        # Step 3: BGM
        yield self._sse_event("progress", {"step": "bgm", "progress": 70, "message": "获取背景音乐..."})
        bgm_path = output_dir / "bgm_raw.wav"
        bgm_file = await bgm_client.get_bgm(bgm_style, str(bgm_path))

        # Step 4: 混音
        yield self._sse_event("progress", {"step": "mixing", "progress": 80, "message": "混音合成中..."})
        final_path = Path(settings.audio_output_dir) / "final" / f"{chapter_id}.mp3"
        await mixer.mix(tts_segments, bgm_file, str(final_path))

        yield self._sse_event("progress", {"step": "done", "progress": 100, "message": "生成完成！"})
        yield self._sse_event("result", {
            "file_path": str(final_path),
            "duration_seconds": sum(s["estimated_duration_ms"] for s in segments) // 1000
        })
        yield self._sse_event("done", {})

    async def _get_voice_map(self, speakers: list) -> dict:
        """从数据库获取角色→参考音频映射"""
        # TODO: 从 Character 表查询 voice_sample
        # 返回 {"冯奇奇": "/path/to/voice_sample.wav", ...}
        return {s: "" for s in speakers}

    def _sse_event(self, event_type: str, data: dict) -> str:
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"

audio_service = AudioGenerationService()
```

- [ ] **Step 2: 创建 audio.py 路由**

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from app.services.audio_service import audio_service
from app.api.common import get_current_user, get_db

router = APIRouter(prefix="/api", tags=["音频"])

@router.post("/chapters/{chapter_id}/audio/generate")
async def generate_audio(chapter_id: str, ...):
    """触发音频生成"""
    # 验证章节存在
    # 创建 AudioTask
    # 返回 task_id
    ...

@router.get("/chapters/{chapter_id}/audio/stream")
async def stream_audio_progress(chapter_id: str, ...):
    """SSE 流式推送生成进度"""
    return StreamingResponse(
        audio_service.generate_audio_stream(chapter_id, chapter_content),
        media_type="text/event-stream"
    )

@router.get("/chapters/{chapter_id}/audio/status")
async def get_audio_status(chapter_id: str, ...):
    ...

@router.get("/chapters/{chapter_id}/audio/download")
async def download_audio(chapter_id: str, ...):
    ...

@router.get("/audio/presets/bgm")
async def list_bgm_presets():
    return {"presets": bgm_client.presets}
```

- [ ] **Step 3: 注册路由到 main.py**

```python
from app.api import audio
app.include_router(audio.router)
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/audio_service.py backend/app/api/audio.py backend/app/main.py
git commit -m "feat: add audio generation service and API routes"
```

---

## Phase 4: 前端改造

### Task 13: 新增 TypeScript 类型

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: 添加音频相关类型**

在文件末尾添加：

```typescript
// ========== 音频相关 ==========

export interface DialogueSegment {
  order: number;
  speaker: string;
  text: string;
  emotion?: string;
  estimated_duration_ms?: number;
}

export interface AudioTask {
  id: string;
  chapter_id: string;
  status: 'queued' | 'parsing' | 'tts' | 'bgm' | 'mixing' | 'done' | 'failed';
  progress: number;
  error_message?: string;
  created_at: string;
}

export interface AudioFile {
  id: string;
  chapter_id: string;
  file_path: string;
  duration_seconds: number;
  file_size_bytes: number;
  format: string;
  created_at: string;
}

export interface VoiceConfig {
  voice_id?: string;
  voice_speed?: number;
  voice_pitch?: number;
  voice_sample?: string;
  catchphrase?: string;
}

export interface BGMPreset {
  id: string;
  name: string;
  style: string;
  tags: string[];
  path?: string;
}

export interface AudioSSEEvent {
  type: 'progress' | 'result' | 'error' | 'done';
  step?: string;
  progress?: number;
  message?: string;
  file_path?: string;
  duration_seconds?: number;
}

export type ContentMode = 'novel' | 'podcast';
```

- [ ] **Step 2: 更新 Character 接口**

```typescript
export interface Character {
  // ... existing fields ...
  voice_id?: string;
  voice_speed?: number;
  voice_pitch?: number;
  voice_sample?: string;
  catchphrase?: string;
}
```

- [ ] **Step 3: 更新 Project 接口**

```typescript
export interface Project {
  // ... existing fields ...
  content_mode?: ContentMode;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add audio/podcast TypeScript types"
```

---

### Task 14: 添加 audioApi 模块

**Files:**
- Modify: `frontend/src/services/api.ts`

- [ ] **Step 1: 在 api.ts 末尾添加**

```typescript
export const audioApi = {
  generate: (chapterId: string, data?: any) =>
    api.post(`/chapters/${chapterId}/audio/generate`, data),

  streamProgress: (chapterId: string): EventSource =>
    new EventSource(`/api/chapters/${chapterId}/audio/stream`),

  getStatus: (chapterId: string) =>
    api.get(`/chapters/${chapterId}/audio/status`),

  download: (chapterId: string) =>
    `/api/chapters/${chapterId}/audio/download`,

  cancel: (taskId: string) =>
    api.delete(`/audio/${taskId}`),

  getBGMPresets: () =>
    api.get('/audio/presets/bgm'),

  uploadVoiceSample: (characterId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/characters/${characterId}/voice-sample`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
  },
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/services/api.ts
git commit -m "feat: add audioApi module to frontend"
```

---

### Task 15: 创建 AudioProgressModal 组件

**Files:**
- Create: `frontend/src/components/AudioProgressModal.tsx`

- [ ] **Step 1: 创建组件**

```tsx
import React, { useState, useEffect, useRef } from 'react';
import { Modal, Progress, List, Tag } from 'antd';
import { SoundOutlined, CheckCircleOutlined, SyncOutlined } from '@ant-design/icons';
import type { AudioSSEEvent } from '../types';

interface Props {
  open: boolean;
  chapterId: string;
  onClose: () => void;
  onDone: (filePath: string) => void;
}

const AudioProgressModal: React.FC<Props> = ({ open, chapterId, onClose, onDone }) => {
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState('');
  const [message, setMessage] = useState('');
  const [steps, setSteps] = useState<{name: string; status: 'wait' | 'process' | 'finish' | 'error'}[]>([
    { name: '解析对话', status: 'wait' },
    { name: '生成语音', status: 'wait' },
    { name: '背景音乐', status: 'wait' },
    { name: '混音合成', status: 'wait' },
  ]);

  useEffect(() => {
    if (!open || !chapterId) return;

    const eventSource = new EventSource(`/api/chapters/${chapterId}/audio/stream`);

    eventSource.onmessage = (event) => {
      const data: AudioSSEEvent = JSON.parse(event.data);

      if (data.type === 'progress') {
        setProgress(data.progress || 0);
        setStep(data.step || '');
        setMessage(data.message || '');

        setSteps(prev => prev.map(s => {
          if (s.name === '解析对话' && data.step === 'tts') return { ...s, status: 'finish' as const };
          if (s.name === '生成语音' && data.step === 'bgm') return { ...s, status: 'finish' as const };
          if (s.name === '背景音乐' && data.step === 'mixing') return { ...s, status: 'finish' as const };
          if (s.name === '混音合成' && data.step === 'done') return { ...s, status: 'finish' as const };
          if (s.name === '解析对话' && data.step === 'parsing') return { ...s, status: 'process' as const };
          if (s.name === '生成语音' && data.step === 'tts') return { ...s, status: 'process' as const };
          if (s.name === '背景音乐' && data.step === 'bgm') return { ...s, status: 'process' as const };
          if (s.name === '混音合成' && data.step === 'mixing') return { ...s, status: 'process' as const };
          return s;
        }));
      }

      if (data.type === 'done' || data.type === 'result') {
        onDone(data.file_path || '');
        eventSource.close();
      }

      if (data.type === 'error') {
        setSteps(prev => prev.map(s => s.name === step ? { ...s, status: 'error' as const } : s));
        eventSource.close();
      }
    };

    return () => eventSource.close();
  }, [open, chapterId]);

  return (
    <Modal
      title="🎙️ 生成播客音频"
      open={open}
      onCancel={onClose}
      footer={null}
      width={500}
    >
      <Progress percent={progress} status={progress === 100 ? 'success' : 'active'} />
      <div style={{ marginTop: 16, marginBottom: 16, color: '#666' }}>
        {message || '准备中...'}
      </div>
      <List
        size="small"
        dataSource={steps}
        renderItem={(item) => (
          <List.Item>
            {item.status === 'finish' && <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />}
            {item.status === 'process' && <SyncOutlined spin style={{ color: '#1890ff', marginRight: 8 }} />}
            {item.status === 'wait' && <SoundOutlined style={{ color: '#d9d9d9', marginRight: 8 }} />}
            {item.name}
          </List.Item>
        )}
      />
    </Modal>
  );
};

export default AudioProgressModal;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/AudioProgressModal.tsx
git commit -m "feat: add AudioProgressModal component with SSE progress tracking"
```

---

### Task 16: 创建 AudioPlayer 组件 + AudioStudio 页面 + 章节按钮

**Files:**
- Create: `frontend/src/components/AudioPlayer.tsx`
- Create: `frontend/src/pages/AudioStudio.tsx`
- Modify: `frontend/src/pages/Chapters.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 AudioPlayer.tsx**

```tsx
import React from 'react';
import { Card, Button, Space, Typography } from 'antd';
import { PlayCircleOutlined, PauseCircleOutlined, DownloadOutlined } from '@ant-design/icons';

interface Props {
  src: string;
  title: string;
  duration: number;
  onDownload: () => void;
}

const AudioPlayer: React.FC<Props> = ({ src, title, duration, onDownload }) => {
  const [playing, setPlaying] = React.useState(false);
  const audioRef = React.useRef<HTMLAudioElement>(null);

  const togglePlay = () => {
    if (playing) {
      audioRef.current?.pause();
    } else {
      audioRef.current?.play();
    }
    setPlaying(!playing);
  };

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  };

  return (
    <Card size="small" style={{ marginBottom: 12 }}>
      <Space>
        <Button
          type="primary"
          shape="circle"
          icon={playing ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
          onClick={togglePlay}
        />
        <div>
          <Typography.Text strong>{title}</Typography.Text>
          <br />
          <Typography.Text type="secondary">{formatDuration(duration)}</Typography.Text>
        </div>
        <Button icon={<DownloadOutlined />} onClick={onDownload}>下载</Button>
      </Space>
      <audio ref={audioRef} src={src} onEnded={() => setPlaying(false)} style={{ display: 'none' }} />
    </Card>
  );
};

export default AudioPlayer;
```

- [ ] **Step 2: 创建 AudioStudio.tsx（音频工作室简化版）**

页面包含：角色音色配置卡片 + BGM 风格选择 + 生成的音频列表。

- [ ] **Step 3: 在 Chapters.tsx 添加生成播客按钮**

在章节操作按钮区域添加：

```tsx
{project?.content_mode === 'podcast' && (
  <Button
    icon={<SoundOutlined />}
    onClick={() => {
      setSelectedChapterId(chapter.id);
      setAudioModalOpen(true);
    }}
  >
    生成播客
  </Button>
)}
```

- [ ] **Step 4: 在 App.tsx 添加路由**

```tsx
import AudioStudio from './pages/AudioStudio';

// 在 project/:projectId 的子路由中添加:
<Route path="audio-studio" element={<AudioStudio />} />
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AudioPlayer.tsx frontend/src/pages/AudioStudio.tsx frontend/src/pages/Chapters.tsx frontend/src/App.tsx
git commit -m "feat: add AudioPlayer, AudioStudio page, podcast button in Chapters"
```

---

## Phase 5: 部署配置

### Task 17: 更新 Dockerfile + requirements.txt

**Files:**
- Modify: `Dockerfile`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Dockerfile 添加 FFmpeg**

在 `apt-get install` 行中添加 `ffmpeg`：

```dockerfile
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    netcat-traditional \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

- [ ] **Step 2: requirements.txt 添加依赖**

```
# 音频处理
ffmpeg-python==0.2.0
```

- [ ] **Step 3: Commit**

```bash
git add Dockerfile backend/requirements.txt
git commit -m "feat: add FFmpeg to Dockerfile and Python dependencies"
```

---

## 验证清单

- [ ] 数据库迁移在 PostgreSQL 上成功执行
- [ ] 播客项目创建 → 播客大纲生成 → 播客剧集生成（输出【角色名】格式）
- [ ] 对话解析器正确提取所有 speaker 和 text
- [ ] ComfyUI 连接测试：`curl http://host.docker.internal:8188/system_stats`
- [ ] 音色参考音频上传 → 存储到正确路径
- [ ] 音频生成流水线端到端（parsing → tts → bgm → mixing → download）
- [ ] AudioProgressModal SSE 推送进度正常
- [ ] 下载的 MP3 可正常播放
- [ ] 小说模式功能不受影响（回归测试）
