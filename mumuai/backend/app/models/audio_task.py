"""音频生成任务模型"""
from sqlalchemy import Column, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AudioTask(Base):
    """音频生成任务表"""
    __tablename__ = "audio_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(20), default="queued", comment="queued/parsing/tts/bgm/mixing/done/failed")
    dialogue_json = Column(JSON, nullable=True, comment="解析后的对话结构")
    bgm_prompt = Column(Text, nullable=True, comment="BGM 生成提示词")
    progress = Column(Float, default=0, comment="进度百分比 0-100")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    chapter = relationship("Chapter", backref="audio_tasks")
    project = relationship("Project", backref="audio_tasks")

    def __repr__(self):
        return f"<AudioTask(id={self.id}, status={self.status})>"
