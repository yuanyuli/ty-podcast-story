"""音频 API 路由"""
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.common import verify_project_access
from app.models.audio_task import AudioTask
from app.models.audio_file import AudioFile
from app.models.chapter import Chapter
from app.services.audio_service import audio_service
from app.services.bgm_client import bgm_client
from app.schemas.audio import (
    AudioTaskResponse,
    AudioFileResponse,
    BGMPreset,
    AudioGenerateRequest,
)
from app.logger import get_logger

router = APIRouter(prefix="/api", tags=["音频"])
logger = get_logger(__name__)


@router.post("/chapters/{chapter_id}/audio/generate", response_model=AudioTaskResponse)
async def generate_audio(
    chapter_id: str,
    req: AudioGenerateRequest = AudioGenerateRequest(),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """触发音频生成，返回 AudioTask"""
    user_id = getattr(request.state, "user_id", None) if request else None

    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, detail="章节不存在")

    await verify_project_access(chapter.project_id, user_id, db)

    if not chapter.content:
        raise HTTPException(400, detail="章节内容为空，请先生成播客内容")

    task = AudioTask(
        chapter_id=chapter_id,
        project_id=chapter.project_id,
        status="queued",
        bgm_prompt=req.bgm_style,
        progress=0,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    logger.info(f"创建音频任务 {task.id} → 章节 {chapter_id}")
    return task


@router.get("/chapters/{chapter_id}/audio/stream")
async def stream_audio_progress(
    chapter_id: str,
    bgm_style: str = "ancient children adventure",
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """SSE 流式推送音频生成进度"""
    user_id = getattr(request.state, "user_id", None) if request else None

    chapter_result = await db.execute(
        select(Chapter).where(Chapter.id == chapter_id)
    )
    chapter = chapter_result.scalar_one_or_none()
    if not chapter:
        raise HTTPException(404, detail="章节不存在")

    await verify_project_access(chapter.project_id, user_id, db)

    if not chapter.content:
        raise HTTPException(400, detail="章节内容为空")

    # 查找或创建 AudioTask
    task_result = await db.execute(
        select(AudioTask)
        .where(AudioTask.chapter_id == chapter_id)
        .order_by(AudioTask.created_at.desc())
        .limit(1)
    )
    task = task_result.scalar_one_or_none()

    if not task:
        task = AudioTask(
            chapter_id=chapter_id,
            project_id=chapter.project_id,
            status="queued",
            bgm_prompt=bgm_style,
            progress=0,
        )
        db.add(task)
        await db.commit()
        await db.refresh(task)

    return StreamingResponse(
        audio_service.generate_audio_stream(
            task=task,
            chapter_content=chapter.content,
            bgm_style=task.bgm_prompt or bgm_style,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/chapters/{chapter_id}/audio/status", response_model=AudioTaskResponse)
async def get_audio_status(
    chapter_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """查询音频生成状态"""
    user_id = getattr(request.state, "user_id", None) if request else None

    task_result = await db.execute(
        select(AudioTask)
        .where(AudioTask.chapter_id == chapter_id)
        .order_by(AudioTask.created_at.desc())
        .limit(1)
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, detail="未找到音频任务")

    await verify_project_access(task.project_id, user_id, db)
    return task


@router.get("/chapters/{chapter_id}/audio/download")
async def download_audio(
    chapter_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """下载最终 MP3 文件"""
    user_id = getattr(request.state, "user_id", None) if request else None

    file_result = await db.execute(
        select(AudioFile)
        .where(AudioFile.chapter_id == chapter_id)
        .order_by(AudioFile.created_at.desc())
        .limit(1)
    )
    audio_file = file_result.scalar_one_or_none()
    if not audio_file or not audio_file.file_path:
        raise HTTPException(404, detail="未找到音频文件")

    await verify_project_access(audio_file.project_id, user_id, db)

    from pathlib import Path
    path = Path(audio_file.file_path)
    if not path.exists():
        raise HTTPException(404, detail="音频文件不存在于磁盘")

    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=f"episode_{chapter_id[-8:]}.mp3",
    )


@router.get("/audio/presets/bgm")
async def list_bgm_presets():
    """获取 BGM 预设列表"""
    bgm_client._load_presets()
    return {
        "presets": [
            BGMPreset(
                id=p["id"],
                name=p["name"],
                style=p.get("tags", [])[-1] if p.get("tags") else "",
                tags=p.get("tags", []),
                path=p.get("path"),
            )
            for p in bgm_client.presets
        ]
    }


@router.delete("/audio/{task_id}")
async def cancel_audio_task(
    task_id: str,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """取消/删除音频任务"""
    user_id = getattr(request.state, "user_id", None) if request else None

    task_result = await db.execute(
        select(AudioTask).where(AudioTask.id == task_id)
    )
    task = task_result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, detail="任务不存在")

    await verify_project_access(task.project_id, user_id, db)

    files_result = await db.execute(
        select(AudioFile).where(AudioFile.task_id == task_id)
    )
    for af in files_result.scalars().all():
        await db.delete(af)

    await db.delete(task)
    await db.commit()

    return {"message": "任务已取消"}
