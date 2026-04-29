# 🎙️ 团团播客故事工坊

> AI 驱动的儿童播客内容创作平台 — 从故事生成到多角色配音，一站式制作广播剧级儿童睡前故事。

## 项目简介

**团团播客故事工坊** 是由 [MuMuAINovel](https://github.com/yuanyuli/MuMuAINovel) 二创而来的 AI 播客工作室。它在原有 AI 小说创作能力的基础上，增加了**播客内容模式**，支持：

- 🎭 **多角色对话体故事生成** — AI 自动生成【旁白】+【角色名】格式的广播剧脚本
- 🎤 **多音色 TTS 语音合成** — 集成 CosyVoice 2.0（通过 ComfyUI），支持零样本音色克隆
- 🎵 **智能背景音乐** — 支持 ACE-Step AI 音乐生成 + 预置 BGM 库兜底
- 🎧 **一键混音导出** — FFmpeg 自动对齐、混音，输出 128kbps MP3

### 首个系列：《冯奇奇的封神榜冒险记》

一部儿童历史穿越广播剧，冯奇奇和他的小伙伴们在封神榜的世界里展开奇妙冒险。每集 5-8 分钟，寓教于乐，适合 3-10 岁儿童收听。

## 技术架构

```
┌───────────────── Docker Network: shared-net ─────────────────┐
│                                                                │
│  shared-postgres    PostgreSQL 18 · 独立共享数据库              │
│  new-api            LLM 中转代理 (One API)                     │
│  mumuainovel        FastAPI + React · 应用主容器               │
│                                                                │
└────────────────────────────────────────────────────────────────┘
                              │
                              │ host.docker.internal:8188
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  宿主机 (Windows, GPU)                                        │
│  ComfyUI :8188                                                │
│    ├── CosyVoice 2.0 节点 (TTS 语音生成)                     │
│    └── ACE-Step 节点 (BGM 音乐生成, 可选)                     │
└──────────────────────────────────────────────────────────────┘
```

### 音频生成流水线

```
AI 生成播客文本 → 对话解析 → 多角色 TTS → BGM 获取 → FFmpeg 混音 → MP3 导出
```

## 快速开始

### 环境要求

- Docker & Docker Compose
- Windows 10+ / Linux
- （可选）NVIDIA GPU + ComfyUI（用于本地 TTS）

### 部署步骤

```bash
# 1. 克隆仓库
git clone https://github.com/yuanyuli/ty-podcast-story.git
cd ty-podcast-story/mumuai

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env — 填入 AI API 密钥和数据库密码

# 3. 创建 Docker 网络
docker network create shared-net

# 4. 启动共享数据库
docker run -d --name shared-postgres \
  --network shared-net \
  -e POSTGRES_PASSWORD=your_password \
  -p 5432:5432 \
  postgres:18

# 5. 构建并启动应用
docker build -t mumuainovel .
docker run -d --name mumuainovel \
  --network shared-net \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  mumuainovel
```

访问 `http://localhost:8000` 即可使用。

## 项目结构

```
mumuai/
├── backend/                    # FastAPI 后端
│   ├── app/
│   │   ├── api/               # API 路由
│   │   │   ├── chapters.py    # 章节管理（含播客模式分支）
│   │   │   ├── audio.py       # 音频生成 API（新增）
│   │   │   └── ...
│   │   ├── models/            # SQLAlchemy 数据模型
│   │   ├── services/          # 业务逻辑
│   │   │   ├── prompt_service.py  # 提示词模板系统
│   │   │   ├── audio_service.py   # 音频生成服务（新增）
│   │   │   └── ...
│   │   └── config.py          # 配置管理
│   └── requirements.txt
├── frontend/                   # React 前端
│   ├── src/
│   │   ├── pages/
│   │   │   ├── AudioStudio.tsx # 音频工作室（新增）
│   │   │   └── ...
│   │   ├── components/
│   │   │   ├── AudioPlayer.tsx # 音频播放器（新增）
│   │   │   └── ...
│   │   └── services/
│   │       └── audioApi.ts     # 音频 API 模块（新增）
│   └── package.json
├── docs/                       # 设计文档
│   └── superpowers/
│       ├── specs/              # 技术规格
│       └── plans/              # 实施计划
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 播客模式 vs 小说模式

| 维度 | 小说模式 | 播客模式 |
|------|----------|----------|
| 核心单位 | 章 (Chapter) | 集 (Episode) |
| 内容格式 | 散文体 | 【旁白】+【角色名】对话体 |
| 字数目标 | ~3000字/章 | 1500-2500字/集 |
| 结尾要求 | 章节完整 | 悬念钩子 + 晚安告别 |
| 大纲结构 | 情节弧线 | 历史时期 + 知识点 + 角色聚焦 |
| 输出产物 | 文本 | 文本 + MP3 音频 |

## 创作工作流

1. **创建项目** → 选择「播客模式」→ 设定世界观和角色
2. **生成剧集大纲** → AI 自动规划历史知识点和悬念设计
3. **生成单集内容** → AI 输出广播剧格式对话体
4. **角色音色配置** → 上传参考音频或选择预设音色
5. **一键生成音频** → TTS + BGM + 混音，下载 MP3

## 技术栈

- **后端**: Python FastAPI + SQLAlchemy + PostgreSQL
- **前端**: React + TypeScript + Vite
- **AI**: OpenAI / Gemini / Claude API（多模型支持）
- **TTS**: CosyVoice 2.0（通过 ComfyUI）
- **音乐**: ACE-Step 1.5（可选）+ 预置 BGM 库
- **混音**: FFmpeg
- **部署**: Docker + Docker Compose

## 路线图

- [x] Phase 1: 基础设施（数据库迁移 + 配置）
- [x] Phase 2: 播客内容模式（Prompt 模板 + 对话解析）
- [ ] Phase 3: TTS 集成（CosyVoice 2.0 + ComfyUI）
- [ ] Phase 4: BGM + FFmpeg 混音
- [ ] Phase 5: 前端音频工作室
- [ ] Phase 6: 喜马拉雅发布集成

## 致谢

本项目基于 [MuMuAINovel](https://github.com/yuanyuli/MuMuAINovel) 二创开发，感谢原项目的优秀架构设计。

## 许可证

MIT License
