#!/bin/bash

# 设置数据库为 SQLite
export DATABASE_URL=sqlite+aiosqlite:///data/ai_story.db

# 设置 HuggingFace 镜像
export HF_ENDPOINT=https://hf-mirror.com
export TRANSFORMERS_OFFLINE=0

# 启动服务
.venv/bin/python -m uvicorn app.main:app --host localhost --port 8000 --reload
