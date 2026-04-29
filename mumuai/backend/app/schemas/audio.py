"""音频相关 Pydantic Schemas"""
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DialogueSegment(BaseModel):
    """对话片段"""
    order: int
    speaker: str
    text: str
    emotion: Optional[str] = "neutral"
    estimated_duration_ms: Optional[int] = 0


class AudioGenerateRequest(BaseModel):
    """音频生成请求"""
    bgm_style: Optional[str] = None
    voice_overrides: Optional[dict] = None


class AudioTaskResponse(BaseModel):
    """音频任务响应"""
    id: str
    chapter_id: str
    status: str
    progress: float
    error_message: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AudioFileResponse(BaseModel):
    """音频文件响应"""
    id: str
    chapter_id: str
    file_path: str
    duration_seconds: Optional[int] = None
    file_size_bytes: Optional[int] = None
    format: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BGMPreset(BaseModel):
    """BGM 预设"""
    id: str
    name: str
    style: str
    tags: List[str]
    path: Optional[str] = None


class VoiceSampleUploadResponse(BaseModel):
    """音色参考音频上传响应"""
    voice_sample: str
    message: str
