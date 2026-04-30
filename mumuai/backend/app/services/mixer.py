"""FFmpeg 混音模块"""
import asyncio
from pathlib import Path
from typing import List


class AudioMixer:
    """多段 TTS 语音 + BGM 混音为最终 MP3"""

    async def mix(
        self,
        tts_segments: List[dict],
        bgm_path: str,
        output_path: str,
        bgm_volume: float = 0.15,
        fade_in: float = 2.0,
        fade_out: float = 3.0,
    ) -> str:
        """
        将多段 TTS 语音和 BGM 混音为最终 MP3。

        Args:
            tts_segments: TTS 片段列表 [{"path": "...", "order": 1}, ...]
            bgm_path: 背景音乐文件路径
            output_path: 输出 MP3 路径
            bgm_volume: BGM 音量比例 (0-1)
            fade_in: 淡入秒数
            fade_out: 淡出秒数

        Returns:
            输出文件路径
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        tts_segments.sort(key=lambda s: s["order"])
        temp_dir = Path(output_path).parent

        # 1. 拼接所有 TTS 片段
        concat_file = temp_dir / "concat_list.txt"
        concat_content = "\n".join(
            f"file '{seg['path']}'" for seg in tts_segments
        )
        concat_file.write_text(concat_content, encoding="utf-8")

        speech_output = temp_dir / "speech_combined.wav"
        cmd_concat = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(speech_output),
        ]
        await self._run_ffmpeg(cmd_concat)

        # 2. 混音：语音 + BGM，输出 MP3
        cmd_mix = [
            "ffmpeg", "-y",
            "-i", str(speech_output),
            "-i", bgm_path,
            "-filter_complex",
            (
                f"[1:a]volume={bgm_volume},"
                f"afade=t=in:d={fade_in},"
                f"afade=t=out:d={fade_out}[bgm];"
                f"[0:a][bgm]amix=inputs=2:duration=first[out]"
            ),
            "-map", "[out]",
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            str(output_path),
        ]
        await self._run_ffmpeg(cmd_mix)

        # 清理临时文件
        concat_file.unlink(missing_ok=True)
        speech_output.unlink(missing_ok=True)

        return output_path

    async def _run_ffmpeg(self, cmd: List[str]):
        """运行 FFmpeg 命令"""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")


mixer = AudioMixer()
