"""对话解析器：从广播剧文本中提取结构化对话段"""
import re
from typing import List, Dict, Any


def parse_dialogue(text: str) -> List[Dict[str, Any]]:
    """
    解析【角色名】格式的广播剧文本，返回 dialogue_json 结构。

    Args:
        text: 包含【角色名】标注的广播剧文本

    Returns:
        [{"order": 1, "speaker": "旁白", "text": "...", "emotion": "neutral", "estimated_duration_ms": 0}, ...]
    """
    pattern = r'【(.+?)】(.+?)(?=【|$)'
    matches = re.findall(pattern, text, re.DOTALL)

    if not matches:
        # 降级：未匹配【角色名】格式时，整段非空文本归为【旁白】
        cleaned = text.strip()
        if not cleaned:
            return []
        return [{
            "order": 1,
            "speaker": "旁白",
            "text": cleaned,
            "emotion": "neutral",
            "estimated_duration_ms": len(cleaned) * 250
        }]

    segments = []
    for i, (speaker, content) in enumerate(matches):
        content = content.strip()
        # 估算时长：中文约 4字/秒，250ms/字
        estimated_ms = len(content) * 250

        segments.append({
            "order": i + 1,
            "speaker": speaker.strip(),
            "text": content,
            "emotion": "neutral",
            "estimated_duration_ms": estimated_ms
        })

    return segments


def validate_podcast_format(text: str) -> Dict[str, Any]:
    """
    验证广播剧文本是否符合格式要求。

    Returns:
        {"valid": bool, "errors": [], "warnings": [], "stats": {}}
    """
    result = {"valid": True, "errors": [], "warnings": [], "stats": {}}

    # 检查是否有【旁白】标签
    if "【旁白】" not in text:
        result["errors"].append("缺少【旁白】标签")
        result["valid"] = False

    # 统计角色
    segments = parse_dialogue(text)
    speakers = list(dict.fromkeys(s["speaker"] for s in segments))
    result["stats"]["speakers"] = speakers
    result["stats"]["segment_count"] = len(segments)

    # 字数检查（1500-2500 为目标）
    total_chars = len(text.replace('\n', '').replace(' ', ''))
    result["stats"]["total_chars"] = total_chars
    if total_chars < 1000:
        result["warnings"].append(f"字数偏少({total_chars}), 建议1500-2500字")
    elif total_chars > 3000:
        result["warnings"].append(f"字数偏多({total_chars}), 可能超过8分钟")

    # 检查单段对话是否过长
    for seg in segments:
        if len(seg["text"]) > 100:
            result["warnings"].append(
                f"第{seg['order']}段({seg['speaker']})对话过长({len(seg['text'])}字)"
            )

    return result
