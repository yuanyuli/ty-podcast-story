"""ComfyUI VoxCPM TTS 客户端"""
import json
import time
import asyncio
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings


class ComfyUITTSClient:
    """ComfyUI VoxCPM TTS HTTP 客户端"""

    def __init__(self):
        self.base_url = settings.comfyui_base_url.rstrip("/")
        self.timeout = settings.comfyui_timeout

    async def generate_speech(
        self,
        text: str,
        voice_sample_path: str,
        speed: float = 1.0,
        output_dir: str = "/app/data/audio/temp",
    ) -> str:
        """
        调用 ComfyUI VoxCPM 生成语音。

        Args:
            text: 要合成的文本
            voice_sample_path: 参考音频路径（zero-shot 音色克隆）
            speed: 语速 (0.5-2.0)
            output_dir: 输出目录

        Returns:
            生成的 WAV 文件路径
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        workflow = self._build_workflow(text, voice_sample_path, speed)

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{self.base_url}/prompt",
                json={"prompt": workflow},
            )
            resp.raise_for_status()
            prompt_data = resp.json()
            prompt_id = prompt_data.get("prompt_id")
            if not prompt_id:
                raise RuntimeError(f"ComfyUI 返回无 prompt_id: {prompt_data}")

            output_file = await self._poll_result(client, prompt_id, output_dir)
            return output_file

    async def _poll_result(
        self,
        client: httpx.AsyncClient,
        prompt_id: str,
        output_dir: str,
    ) -> str:
        """轮询 ComfyUI 任务状态直到完成"""
        deadline = time.time() + self.timeout

        while time.time() < deadline:
            history_resp = await client.get(
                f"{self.base_url}/history/{prompt_id}"
            )
            history_resp.raise_for_status()
            history = history_resp.json()

            if prompt_id in history:
                outputs = history[prompt_id].get("outputs", {})
                for node_id, node_output in outputs.items():
                    audio_files = node_output.get("audio", [])
                    if audio_files:
                        filename = audio_files[0].get("filename", "output.wav")
                        output_path = Path(self.base_url).parent / "output" / filename
                        return str(output_path)

            await asyncio.sleep(1)

        raise TimeoutError(f"TTS 生成超时 ({self.timeout}s)")

    def _build_workflow(
        self, text: str, reference_audio: str, speed: float
    ) -> dict:
        """构建 ComfyUI VoxCPM workflow JSON"""
        return {
            "3": {
                "class_type": "VoxCPM_TTS",
                "inputs": {
                    "text": text,
                    "reference_audio": reference_audio,
                    "speed": speed,
                    "seed": int(time.time()),
                },
            },
            "4": {
                "class_type": "SaveAudio",
                "inputs": {
                    "filename_prefix": "tts_output",
                    "audio": ["3", 0],
                },
            },
        }


tts_client = ComfyUITTSClient()
