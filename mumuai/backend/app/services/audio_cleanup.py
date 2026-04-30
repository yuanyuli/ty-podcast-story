"""临时音频文件清理服务"""
import asyncio
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from app.config import settings


class AudioCleanupService:
    """清理 audio_tasks 完成/失败后的临时文件"""

    async def cleanup_temp_files(self, task_id: str):
        """立即清理指定 task 的临时文件"""
        temp_dir = Path(settings.audio_output_dir) / "temp" / task_id
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def cleanup_old_temp_dirs(self, max_age_hours: int = 24):
        """清理超过 max_age_hours 的临时目录"""
        temp_root = Path(settings.audio_output_dir) / "temp"
        if not temp_root.exists():
            return

        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        for dir_path in temp_root.iterdir():
            if dir_path.is_dir():
                mtime = datetime.fromtimestamp(dir_path.stat().st_mtime)
                if mtime < cutoff:
                    shutil.rmtree(dir_path, ignore_errors=True)

    async def run_periodic_cleanup(self, interval_hours: int = 6):
        """后台定时清理循环"""
        while True:
            await asyncio.sleep(interval_hours * 3600)
            await self.cleanup_old_temp_dirs()


cleanup_service = AudioCleanupService()
