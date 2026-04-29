"""音频文件模型"""
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import uuid


class AudioFile(Base):
    """音频文件表"""
    __tablename__ = "audio_files"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String(36), ForeignKey("audio_tasks.id", ondelete="CASCADE"), nullable=False)
    chapter_id = Column(String(36), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(500), nullable=True, comment="文件路径")
    duration_seconds = Column(Integer, nullable=True, comment="音频时长（秒）")
    file_size_bytes = Column(Integer, nullable=True, comment="文件大小（字节）")
    format = Column(String(10), default="mp3", comment="音频格式")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")

    task = relationship("AudioTask", backref="audio_files")
    chapter = relationship("Chapter", backref="audio_files")
    project = relationship("Project", backref="audio_files")

    def __repr__(self):
        return f"<AudioFile(id={self.id}, format={self.format})>"
