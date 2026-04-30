"""BGM 音乐生成客户端：ACE-Step + 预置库兜底"""
import json
import random
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings


class BGMClient:
    """BGM 获取：ACE-Step API 优先，预置库兜底"""

    def __init__(self):
        self.acestep_url = settings.acestep_api_url
        self.presets: list[dict] = []
        self._presets_loaded = False

    async def get_bgm(self, style: str, output_path: str) -> str:
        """获取背景音乐

        Args:
            style: BGM 风格描述
            output_path: 输出文件路径（ACE-Step 生成时使用）

        Returns:
            BGM 文件路径
        """
        if self.acestep_url:
            try:
                return await self._generate_acestep(style, output_path)
            except Exception:
                pass

        return self._match_preset(style)

    async def _generate_acestep(self, style: str, output_path: str) -> str:
        """调用 ACE-Step API 生成 BGM"""
        async with httpx.AsyncClient(
            timeout=settings.acestep_timeout
        ) as client:
            resp = await client.post(
                f"{self.acestep_url}/generate",
                json={
                    "prompt": f"instrumental background music, {style}, "
                    f"gentle, children's story"
                },
            )
            resp.raise_for_status()
            data = resp.json()

            audio_url = data.get("audio_url")
            if audio_url:
                audio_resp = await client.get(audio_url)
                audio_resp.raise_for_status()
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                Path(output_path).write_bytes(audio_resp.content)
                return output_path

            raise Exception("ACE-Step 未返回音频 URL")

    def _match_preset(self, style: str) -> str:
        """从预置 BGM 库匹配最合适的音乐"""
        if not self._presets_loaded:
            self._load_presets()

        style_lower = style.lower()
        matches = [
            p for p in self.presets
            if any(tag in style_lower for tag in p.get("tags", []))
        ]

        if matches:
            return random.choice(matches)["path"]

        if self.presets:
            return random.choice(self.presets)["path"]

        return ""

    def _load_presets(self):
        """加载预置 BGM 列表"""
        presets_file = (
            Path(settings.audio_output_dir)
            / settings.bgm_presets_dir
            / "index.json"
        )
        if presets_file.exists():
            self.presets = json.loads(presets_file.read_text(encoding="utf-8"))
        else:
            self.presets = [
                {
                    "id": "calm_morning",
                    "name": "宁静清晨",
                    "tags": ["calm", "morning", "gentle"],
                    "path": "",
                },
                {
                    "id": "ancient_city",
                    "name": "古城漫步",
                    "tags": ["ancient", "city", "adventure"],
                    "path": "",
                },
                {
                    "id": "mystery_forest",
                    "name": "神秘森林",
                    "tags": ["mystery", "nature", "wonder"],
                    "path": "",
                },
                {
                    "id": "happy_ending",
                    "name": "快乐结尾",
                    "tags": ["happy", "warm", "ending"],
                    "path": "",
                },
            ]
        self._presets_loaded = True


bgm_client = BGMClient()
