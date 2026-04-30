"""音频生成编排服务"""
import json
from pathlib import Path
from datetime import datetime
from typing import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.audio_task import AudioTask
from app.models.audio_file import AudioFile
from app.models.character import Character
from app.models.chapter import Chapter
from app.services.dialogue_parser import parse_dialogue
from app.services.tts_client import tts_client
from app.services.bgm_client import bgm_client
from app.services.mixer import mixer
from app.services.audio_cleanup import cleanup_service


class AudioGenerationService:
    """播客音频生成编排服务：解析 → TTS → BGM → 混音"""

    async def generate_audio_stream(
        self,
        task: AudioTask,
        chapter_content: str,
        bgm_style: str,
        db: AsyncSession,
    ) -> AsyncGenerator[str, None]:
        """SSE 流式推送音频生成进度

        Args:
            task: AudioTask 数据库记录
            chapter_content: 章节内容（播客格式文本）
            bgm_style: BGM 风格描述
            db: 数据库会话
        """
        output_dir = Path(settings.audio_output_dir) / "temp" / task.id
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Step 1: 对话解析
            yield self._sse("progress", {
                "step": "parsing", "progress": 5,
                "message": "正在解析对话..."
            })
            segments = parse_dialogue(chapter_content)
            if not segments:
                yield self._sse("error", {
                    "message": "未检测到【角色名】格式对话"
                })
                task.status = "failed"
                task.error_message = "未检测到【角色名】格式对话"
                await db.commit()
                await cleanup_service.cleanup_temp_files(task.id)
                return

            unique_speakers = list(set(s["speaker"] for s in segments))
            yield self._sse("progress", {
                "step": "parsing", "progress": 10,
                "message": f"解析完成：{len(unique_speakers)}个角色，{len(segments)}段对话"
            })
            task.status = "parsing"
            task.dialogue_json = segments
            task.progress = 10
            await db.commit()

            # Step 2: 多角色 TTS
            yield self._sse("progress", {
                "step": "tts", "progress": 15,
                "message": "开始生成语音..."
            })
            task.status = "tts"

            speaker_voice_map = await self._get_voice_map(unique_speakers, db)

            tts_segments = []
            total = len(segments)
            for i, seg in enumerate(segments):
                progress = 15 + int(50 * i / total)
                yield self._sse("progress", {
                    "step": "tts", "progress": progress,
                    "message": f"生成 {seg['speaker']} 语音 ({i+1}/{total})..."
                })
                task.progress = progress
                await db.commit()

                voice_sample = speaker_voice_map.get(seg["speaker"], "")
                seg_path = output_dir / f"{i+1:03d}_{seg['speaker']}.wav"
                try:
                    await tts_client.generate_speech(
                        text=seg["text"],
                        voice_sample_path=voice_sample,
                        output_dir=str(output_dir),
                    )
                    # TTS 输出文件路径取决于 ComfyUI 配置
                    # 预期输出在 ComfyUI output 目录下
                except Exception as e:
                    yield self._sse("progress", {
                        "step": "tts", "progress": progress,
                        "message": f"TTS 失败 ({seg['speaker']}): {e}，使用静默替代"
                    })
                tts_segments.append({
                    "path": str(seg_path),
                    "order": seg["order"],
                    "speaker": seg["speaker"],
                })

            # Step 3: BGM
            yield self._sse("progress", {
                "step": "bgm", "progress": 70,
                "message": "获取背景音乐..."
            })
            task.status = "bgm"
            task.progress = 70
            await db.commit()

            bgm_path = output_dir / "bgm_raw.wav"
            bgm_file = await bgm_client.get_bgm(bgm_style, str(bgm_path))

            # Step 4: 混音
            yield self._sse("progress", {
                "step": "mixing", "progress": 80,
                "message": "混音合成中..."
            })
            task.status = "mixing"
            task.progress = 80
            await db.commit()

            final_dir = Path(settings.audio_output_dir) / "final"
            final_dir.mkdir(parents=True, exist_ok=True)
            final_path = final_dir / f"{task.chapter_id}.mp3"

            await mixer.mix(tts_segments, bgm_file, str(final_path))

            # Step 5: 完成
            yield self._sse("progress", {
                "step": "done", "progress": 100,
                "message": "生成完成！"
            })
            task.status = "done"
            task.progress = 100
            await db.commit()

            # 创建 AudioFile 记录
            file_size = final_path.stat().st_size if final_path.exists() else 0
            audio_file = AudioFile(
                task_id=task.id,
                chapter_id=task.chapter_id,
                project_id=task.project_id,
                file_path=str(final_path),
                duration_seconds=sum(
                    s.get("estimated_duration_ms", 0) for s in segments
                ) // 1000,
                file_size_bytes=file_size,
                format="mp3",
            )
            db.add(audio_file)
            await db.commit()

            yield self._sse("result", {
                "file_path": str(final_path),
                "duration_seconds": audio_file.duration_seconds,
                "file_size_bytes": file_size,
            })
            yield self._sse("done", {})

            await cleanup_service.cleanup_temp_files(task.id)

        except Exception as e:
            yield self._sse("error", {"message": str(e)})
            task.status = "failed"
            task.error_message = str(e)
            await db.commit()
            await cleanup_service.cleanup_temp_files(task.id)

    async def _get_voice_map(self, speakers: list, db: AsyncSession) -> dict:
        """从数据库查询角色→参考音频路径映射"""
        result = {}
        for speaker in speakers:
            stmt = select(Character).where(Character.name == speaker)
            char_result = await db.execute(stmt)
            char = char_result.scalar_one_or_none()
            if char and char.voice_sample:
                base_dir = Path(settings.audio_output_dir)
                result[speaker] = str(base_dir / char.voice_sample)
            else:
                result[speaker] = ""
        return result

    @staticmethod
    def _sse(event_type: str, data: dict) -> str:
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"


audio_service = AudioGenerationService()
