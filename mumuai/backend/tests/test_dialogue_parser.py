"""测试对话解析器"""
from app.services.dialogue_parser import parse_dialogue, validate_podcast_format


def test_parse_dialogue():
    text = "【旁白】商朝末年，朝歌城外...\n【冯奇奇】（揉揉眼睛）咦？这是哪儿？\n【旁白】远处，一个白发老者走来..."
    result = parse_dialogue(text)
    assert len(result) == 3
    assert result[0]["speaker"] == "旁白"
    assert result[1]["speaker"] == "冯奇奇"
    assert "揉揉眼睛" in result[1]["text"]


def test_empty_text():
    assert parse_dialogue("") == []
    assert parse_dialogue("   ") == []


def test_fallback_to_narrator():
    """没有【角色名】标签的文本默认归为【旁白】"""
    text = "这是一段没有任何角色标记的普通文本。"
    result = parse_dialogue(text)
    assert len(result) == 1
    assert result[0]["speaker"] == "旁白"
    assert result[0]["text"] == text


def test_validate_podcast_format():
    valid_text = "【旁白】故事开始...\n【冯奇奇】你好！\n【旁白】结束了。"
    result = validate_podcast_format(valid_text)
    assert result["valid"] is True
    assert "旁白" in result["stats"]["speakers"]
    assert "冯奇奇" in result["stats"]["speakers"]
    assert result["stats"]["segment_count"] == 3


def test_validate_missing_narrator():
    """缺少【旁白】标签应该报错"""
    text = "【冯奇奇】你好！\n【五花】我饿了！"
    result = validate_podcast_format(text)
    assert result["valid"] is False
    assert any("【旁白】" in e for e in result["errors"])


def test_validate_too_short():
    """字数太少应该有警告"""
    text = "【旁白】短。"
    result = validate_podcast_format(text)
    assert any("字数偏少" in w for w in result.get("warnings", []))


def test_parse_dialogue_with_multiline():
    """测试多行对话文本"""
    text = """【旁白】商朝末年，朝歌城外的渭水边，一阵奇怪的金色光芒闪过...

【冯奇奇】（揉揉眼睛）咦？我的房间呢？这是哪儿？

【五花】天啊！我闻到烤肉的味道了！好香！

【肥笼】喵呜——！（追着一只烤鸡跑远了）

【旁白】远处，一个白发老者坐在河边，手里拿着一根没有鱼饵的钓竿..."""
    result = parse_dialogue(text)
    assert len(result) == 5
    speakers = [s["speaker"] for s in result]
    assert speakers == ["旁白", "冯奇奇", "五花", "肥笼", "旁白"]


def test_parse_dialogue_single_speaker():
    """只有旁白的文本也应该正常解析"""
    text = "【旁白】这是一个很长很长的故事。\n【旁白】故事还在继续。"
    result = parse_dialogue(text)
    assert len(result) == 2
    assert all(s["speaker"] == "旁白" for s in result)
