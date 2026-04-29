# 冯奇奇的封神榜冒险记 — 播客化改造设计文档

> 日期: 2026-04-29 | 版本: v1.0 | 状态: 待审核

---

## 一、项目概述

### 1.1 背景

将 MuMuAINovel（AI 小说创作工具）改造为 **AI 播客工作室**，支持生成带背景音乐的多角色对话儿童睡前播客，发布在喜马拉雅等平台进行自媒体变现。

### 1.2 产品定位

- **品牌**: 科普冒险路线，寓教于乐
- **首个系列**: 《冯奇奇的封神榜冒险记》
- **内容形式**: 儿童历史穿越广播剧，5-8分钟/集
- **目标受众**: 3-10岁儿童及其家长
- **发布平台**: 喜马拉雅

### 1.3 角色阵容

| 角色 | 类型 | 性格标签 |
|------|------|----------|
| **冯奇奇** | 主角小男孩 | 捣蛋鬼，好奇心爆棚，但心思细腻 |
| **五花** | 小女孩队员 | 吃货，名字谐音五花肉 |
| **布皮冻** | 小男孩队员 | Q弹捣蛋，外表皮内心软 |
| **肥笼** | 宠物猫 | 贪吃但行动矫健 |
| **白木苏** | 大哥哥（保姆苏）| 救场+历史讲解，团队保姆 |
| + 历史人物 | 每集嘉宾 | 姜子牙、哪吒、纣王等 |

### 1.4 技术目标

- 在 MuMuAINovel 上新增 **播客内容模式**（novel / podcast 双模式）
- 集成 **VoxCPM**（TTS 语音生成）通过 ComfyUI
- 集成 **ACE-Step 1.5**（BGM 背景音乐生成，可选，兜底使用预置 BGM 库）
- **FFmpeg** 后期混音，输出 128kbps MP3
- 保留原有小说创作功能，播客模式作为新模块叠加

---

## 二、技术架构

### 2.1 容器部署图

```
┌───────────────── Docker Network: shared-net ─────────────────┐
│                                                                │
│  shared-postgres    PostgreSQL 18 · 独立共享DB                 │
│  new-api            LLM 中转代理 (已存在)                      │
│  mumuainovel        FastAPI + React · 应用主容器                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                              │
                              │ host.docker.internal:8188
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  宿主机 (Windows, GPU)                                        │
│  ComfyUI :8188                                                │
│    ├── VoxCPM 节点 (TTS 语音生成)                             │
│    └── ACE-Step 节点 (BGM 音乐生成, 可选)                     │
│  ACE-Step API :8001 (备选独立部署)                            │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 音频生成流水线

```
AI 生成播客文本 → 对话解析 → 多角色 TTS (VoxCPM) → BGM 获取 (ACE-Step / 预置库)
                                                    ↓
                                               FFmpeg 混音
                                              (对齐 → 淡入淡出 → MP3)
```

### 2.3 数据流

```
User → 触发"生成播客"
  → 对话解析（parse_dialogue → dialogue_json）
  → 多角色 TTS 循环（ComfyUI VoxCPM, per speaker）
  → BGM 来源判断:
      ├── ACE-Step 可用? → ACE-Step API (bgm_raw.wav)
      └── 否 → 预置 BGM 库（标签匹配）
  → FFmpeg 混音 (TTS segments + BGM → final.mp3)
  → 下载
```

### 2.4 共享存储路径

所有音频文件统一存放于 `/app/data/audio/` 下（由 `AUDIO_OUTPUT_DIR` 配置驱动）：

```
/app/data/audio/
├── temp/{task_id}/          # 中间 TTS 片段 (临时, 24h清理)
│   ├── 001_旁白.wav
│   ├── 002_冯奇奇.wav
│   └── bgm_raw.wav
├── final/{project_id}/      # 最终混音结果 (持久)
│   └── {chapter_id}.mp3
└── voice_samples/{char_id}/ # 角色参考音频
    └── reference.wav
```

---

## 三、数据库变更

### 3.1 Project 表：新增 content_mode

```sql
ALTER TABLE projects ADD COLUMN content_mode VARCHAR(20) DEFAULT 'novel';
ALTER TABLE projects ADD CONSTRAINT check_content_mode
    CHECK (content_mode IN ('novel', 'podcast'));
```

### 3.2 Character 表：新增音色字段

```sql
ALTER TABLE characters ADD COLUMN voice_id VARCHAR(100);       -- VoxCPM 音色标识
ALTER TABLE characters ADD COLUMN voice_speed FLOAT DEFAULT 1.0;
ALTER TABLE characters ADD COLUMN voice_pitch FLOAT DEFAULT 0.0;
ALTER TABLE characters ADD COLUMN voice_sample VARCHAR(500);   -- 参考音频路径
ALTER TABLE characters ADD COLUMN catchphrase VARCHAR(200);    -- 口头禅
```

### 3.3 新增 AudioTask 表

```sql
CREATE TABLE audio_tasks (
    id VARCHAR(36) PRIMARY KEY,
    chapter_id VARCHAR(36) REFERENCES chapters(id) ON DELETE CASCADE,
    project_id VARCHAR(36) REFERENCES projects(id) ON DELETE CASCADE,
    status VARCHAR(20) DEFAULT 'queued',  -- queued/parsing/tts/bgm/mixing/done/failed
    dialogue_json JSON,                    -- 解析后的对话结构
    bgm_prompt TEXT,                       -- BGM 生成提示词
    progress FLOAT DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### 3.4 dialogue_json 结构定义

```json
[
  {
    "order": 1,
    "speaker": "旁白",
    "text": "商朝末年，朝歌城外的渭水边...",
    "emotion": "neutral",
    "estimated_duration_ms": 12000
  },
  {
    "order": 2,
    "speaker": "冯奇奇",
    "text": "（揉揉眼睛）咦？我的房间呢？",
    "emotion": "surprised",
    "estimated_duration_ms": 4000
  }
]
```

| 字段 | 类型 | 说明 |
|------|------|------|
| order | int | 发言顺序 |
| speaker | string | 角色名，必须匹配角色表中 name |
| text | string | 该段完整文本（含动作描述） |
| emotion | string | 情绪标签，用于 TTS 情感参数 |
| estimated_duration_ms | int | 估算时长，用于时间轴对齐 |

### 3.5 新增 AudioFile 表

```sql
CREATE TABLE audio_files (
    id VARCHAR(36) PRIMARY KEY,
    task_id VARCHAR(36) REFERENCES audio_tasks(id) ON DELETE CASCADE,
    chapter_id VARCHAR(36) REFERENCES chapters(id) ON DELETE CASCADE,
    project_id VARCHAR(36) REFERENCES projects(id) ON DELETE CASCADE,
    file_path VARCHAR(500),          -- 最终 MP3 路径
    duration_seconds INTEGER,        -- 时长
    file_size_bytes INTEGER,         -- 文件大小
    format VARCHAR(10) DEFAULT 'mp3',
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 3.6 中间音频文件管理

混音前的每段角色 TTS 输出为临时 WAV 文件，存放于 `AUDIO_OUTPUT_DIR/temp/{task_id}/`：

路径统一由 `AUDIO_OUTPUT_DIR` 配置驱动（默认 `/app/data/audio`），中间产物和最终结果都在此目录下，见 2.4 路径规范。

**生命周期**: task 标记 `done` 后 24 小时自动清理（后台定时任务）；task 标记 `failed` 后立即清理。中间文件不写入数据库，仅通过文件系统管理。

### 3.7 音色参考音频管理

**上传 API**: 在现有 `characters` 路由中增加端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| `POST` | `/api/characters/{id}/voice-sample` | 上传参考音频（multipart/form-data, <5MB, WAV/MP3, 后端自动转码为 WAV）|
| `DELETE` | `/api/characters/{id}/voice-sample` | 删除参考音频 |

**存储**: 上传后自动转码为 16kHz 单声道 WAV，存于 `AUDIO_OUTPUT_DIR/voice_samples/{character_id}/reference.wav`，路径写入 `characters.voice_sample` 字段。

**ComfyUI 调用**: TTS 客户端构建 workflow 时，将 `voice_sample` 文件路径作为 VoxCPM 节点的参考音频输入参数传递给 ComfyUI。

---

## 四、播客模式 Prompt 模板设计

### 4.1 新增模板清单

| 模板键 | 用途 | 类别 |
|--------|------|------|
| `PODCAST_OUTLINE` | 播客剧集大纲生成 | 大纲生成 |
| `PODCAST_EPISODE_FIRST` | 第1集内容生成（含开场） | 章节创作 |
| `PODCAST_EPISODE_NEXT` | 后续剧集内容 | 章节创作 |
| `PODCAST_CHARACTER` | 播客角色生成（侧重声音属性） | 角色生成 |
| `PODCAST_WORLD` | 播客世界观（时代背景+声音氛围） | 世界构建 |
| `PODCAST_REGENERATE` | 播客内容重新生成 | 章节重写 |

### 4.2 播客大纲 Structure JSON

```json
{
  "episode_number": 1,
  "title": "掉进封神榜！",
  "historical_period": "商朝末年·纣王时期",
  "historical_figure": "姜子牙",
  "knowledge_point": "姜子牙垂钓渭水——什么叫'愿者上钩'",
  "character_focus": "冯奇奇的首次穿越，五花发现古代美食",
  "scenes": [
    "现代：冯奇奇和五花放学路上的小争吵",
    "穿越：朝歌城集市，肥笼追一只烤鸡",
    "相遇：渭水边遇姜子牙，鱼钩上没有鱼饵",
    "高潮：马蹄声——哪吒踩着风火轮飞来"
  ],
  "emotion": "好奇→惊讶→恍然大悟",
  "cliffhanger": "远处传来马蹄声，一个踩着风火轮的少年朝他们飞来...",
  "bgm_style": "悠远古风+轻快童趣",
  "estimated_duration": "6分钟"
}
```

### 4.3 模板结构说明

播客模板遵循与现有小说模板相同的 RTCO 框架（`<system>` / `<task>` / `<input>` / `<guidelines>` / `<output>` / `<constraints>`），通过 `PromptService.get_template()` 返回完整模板字符串，使用 `PromptService.format_prompt(template, **variables)` 填充变量。与小说模板的不同在于：

- `<output>` 要求输出 `【角色名】对话内容` 格式，而非散文体
- `<constraints>` 增加时长约束（1500-2500字）、悬念钩子尾要求

### 4.4 对话解析映射

`dialogue_parser` 模块通过正则 `【(.+?)】(.+?)(?=【|$)` 解析章节文本，按顺序匹配【角色名】标签，生成 `dialogue_json` 结构（见 3.4）。解析失败的段落默认归为`【旁白】`。

### 4.5 播客内容输出格式

所有播客内容必须遵循以下标注格式：

```
【旁白】商朝末年，朝歌城外的渭水边，一阵奇怪的金色光芒闪过...
【冯奇奇】（揉揉眼睛）咦？我的房间呢？这是哪儿？
【五花】天啊！我闻到烤肉的味道了！好香！
【肥笼】喵呜——！（追着一只烤鸡跑远了）
【布皮冻】五花！那是人家的晚饭！快把肥笼叫回来！
【旁白】远处，一个白发老者坐在河边，手里拿着一根没有鱼饵的钓竿...
【白木苏】别闹了大家，那是姜子牙！商朝最传奇的智者！
【姜子牙】（微微一笑，头也不回）小娃娃们，你们是从哪个朝代来的？
【冯奇奇】朝...朝代？姜爷爷你说什么？
【旁白】就在这时，远处传来雷鸣般的马蹄声，一个踩着风火轮的少年呼啸而来...
【哪吒】（远远喊道）姜师叔！有人擅闯封神台！
【白木苏】（压低声音）完了...这是哪吒。别看他小，他可是三太子...
```

### 4.6 新增写作风格预设

| preset_id | 名称 | prompt_content |
|-----------|------|----------------|
| `podcast_bedtime` | 睡前故事风 | 语速温和、句子简短(单句不超过15字)、多用拟声词和重复句式、每集结尾用"小朋友们，想知道后面发生了什么吗？闭上眼睛，我们明天继续..." |
| `podcast_drama` | 历史广播剧风 | 对话节奏明快、角色性格鲜明、旁白有画面感、适当使用环境音描述、每集结尾设置悬念钩子 |

---

## 五、后端 API 设计

### 5.1 新增路由：app/api/audio.py

| 方法 | 端点 | 说明 |
|------|------|------|
| `POST` | `/api/chapters/{id}/audio/generate` | 触发音频生成，返回 task_id |
| `GET` | `/api/chapters/{id}/audio/stream` | SSE 流式推送生成进度 |
| `GET` | `/api/chapters/{id}/audio/status` | 查询生成状态 |
| `GET` | `/api/chapters/{id}/audio/download` | 下载 MP3 文件 |
| `DELETE` | `/api/audio/{task_id}` | 取消/删除音频 |
| `GET` | `/api/audio/presets/bgm` | BGM 预设标签列表 |

### 5.2 核心服务：app/services/audio_service.py

```python
class AudioGenerationService:
    dialogue_parser   # AI 解析章节文本 → 结构化对话段
    tts_client        # ComfyUI API → VoxCPM 生成语音
    bgm_client        # ACE-Step API / ComfyUI → 生成 BGM
    bgm_matcher       # 预置 BGM 标签匹配（兜底方案）
    mixer             # FFmpeg → 对齐 + 混音 + 导出 MP3
```

### 5.3 章节生成分支（chapters.py 修改）

在 `generate_chapter_content_stream` 方法中增加播客模式分支：

```python
if project.content_mode == 'podcast':
    template_key = 'PODCAST_EPISODE_FIRST' if is_first else 'PODCAST_EPISODE_NEXT'
    template = await PromptService.get_template(template_key, user_id, db)
    # 播客特有变量：historical_period, knowledge_point, cliffhanger
else:
    # 原有小说模式逻辑不变
```

### 5.4 配置管理

在 `app/config.py` 中新增：

```python
# ComfyUI
COMFYUI_BASE_URL: str = "http://host.docker.internal:8188"
COMFYUI_TIMEOUT: int = 300  # TTS 超时秒数

# ACE-Step
ACESTEP_API_URL: str = "http://host.docker.internal:8001"
ACESTEP_TIMEOUT: int = 120  # BGM 超时秒数

# 音频输出
AUDIO_OUTPUT_DIR: str = "/app/data/audio"
AUDIO_FORMAT: str = "mp3"
AUDIO_BITRATE: str = "128k"
```

---

## 六、前端改造

### 6.1 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `pages/Chapters.tsx` | 修改 | 章节列表/编辑器中新增"生成播客"按钮 |
| `pages/AudioStudio.tsx` | **新增** | 音频工作室（角色音色管理 + BGM 预设） |
| `components/AudioPlayer.tsx` | **新增** | 内嵌音频播放器 |
| `components/AudioProgressModal.tsx` | **新增** | 音频生成进度弹窗（复刻 SSEProgressModal 模式） |
| `components/CharacterCard.tsx` | 修改 | 新增音色相关展示/配置入口 |
| `types/index.ts` | 修改 | 新增 AudioTask, AudioFile, VoiceConfig 类型 |
| `services/api.ts` | 修改 | 新增 audioApi 模块 |

### 6.2 项目创建向导改造

在 Wizard 步骤中增加内容模式选择：

```
步骤0: 选择模式 → [小说模式 / 播客模式]
  ↓ 播客模式
步骤1: 播客世界观 → 历史时期、声音氛围、BGM 风格
步骤2: 角色创建 → 含音色参考音频上传
步骤3: 剧集大纲 → 按播客结构生成
```

---

## 七、实施顺序

### Phase 1: 基础设施（优先级最高）
1. 数据库迁移：Project.content_mode, Character.voice_*, AudioTask, AudioFile
2. 后端 config.py 新增 ComfyUI/ACE-Step 配置
3. 后端 audio_service.py 框架搭建

### Phase 2: 播客内容模式
4. 6 个播客 Prompt 模板添加到 PromptService
5. 播客大纲结构定义
6. 对话解析器（dialogue_parser，正则解析【角色名】格式→dialogue_json）
7. chapters.py 生成分支（podcast 模式，生成后自动验证解析）
8. outlines.py 播客大纲生成
9. wizard_stream.py 播客模式向导

### Phase 3: TTS 集成
10. ComfyUI VoxCPM 客户端（tts_client）
11. 音色参考音频上传 API

### Phase 4: BGM + 混音
12. ACE-Step 客户端（bgm_client）
13. BGM 预设库 + 标签匹配
14. FFmpeg 混音模块

### Phase 5: 前端
15. AudioProgressModal
16. AudioPlayer
17. AudioStudio 页面
18. Chapters 页面按钮集成
19. CharacterCard 音色入口

### Phase 6: 部署
20. Dockerfile 更新（加 FFmpeg）
21. 音色参考音频管理
22. 端到端测试

---

## 八、风险和注意事项

1. **ComfyUI API 延迟**: 轮询模式有延迟，大文本时 TTS 可能耗时数分钟。需要合理的超时和重试机制。
2. **GPU 资源**: VoxCPM 和 ACE-Step 共享 GPU，需注意显存管理。建议串行调用避免 OOM。
3. **对话解析准确性**: AI 解析对话归属可能出错，需要人工校对入口。
4. **著作权**: ACE-Step MIT 协议可商用，VoxCPM 需确认商用条款。
5. **品牌一致性**: 项目名保持 MuMuAINovel 还是改名，后续确定。

---

## 九、验证方案

1. **端到端测试**: 创建播客项目 → 生成剧集大纲 → 生成一集内容 → 触发音频生成 → 下载并播放 MP3
2. **质量检查**:
   - 内容格式验证：确认输出遵循【角色名】格式
   - 时长验证：5-8分钟约束
   - 音频质量：主观听感评估
3. **单元测试**: audio_service 各模块独立测试
4. **集成测试**: ComfyUI 连接、ACE-Step 连接、FFmpeg 混音
