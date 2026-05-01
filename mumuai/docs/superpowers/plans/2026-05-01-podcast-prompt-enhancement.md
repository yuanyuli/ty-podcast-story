# 播客提示词全面增强 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增强 6 个播客提示词模板，补全 4 个调用点的变量注入，根治 AI 生成怪异角色和脱离主题的问题。

**Architecture:** 所有改动在服务端 (Python/FastAPI)，不涉及数据库迁移。核心是"补全 RTCO 框架（system/task/input/guidelines/output/constraints）+ 注入完整项目上下文"，让 AI 有足够的围栏约束。

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy / PromptService

---

## 文件结构

| 文件 | 改动类型 | 职责 |
|------|---------|------|
| `backend/app/services/prompt_service.py` | 修改 | 6个播客模板增强 + template_definitions 注册 |
| `backend/app/api/outlines.py` | 修改 | 播客大纲分支注入完整上下文 |
| `backend/app/api/wizard_stream.py` | 修改 | 播客角色生成分支 + 批量模式 |
| `backend/app/api/chapters.py` | 修改 | 剧集分支注入 bgm_style/sound_effects |
| `backend/app/services/auto_character_service.py` | 修改 | 新增播客模式分支 |

---

### Task 1: 增强 PODCAST_WORLD 模板 + 注册

**Files:**
- Modify: `backend/app/services/prompt_service.py:2556-2576`

**增强内容：** 补充 input/constraints 块，扩展 output 字段。

- [ ] **Step 1: 替换 PODCAST_WORLD 模板**

将当前的 PODCAST_WORLD（约 20 行）替换为以下增强版：

```python
PODCAST_WORLD = """<system>
你是专业的儿童广播剧世界观设计师，擅长为3-10岁小朋友打造沉浸式历史穿越故事的世界设定。你的设计既要符合历史真实，又要充满童趣和想象力。
</system>

<task>
根据以下项目信息，设计一个适合儿童睡前广播剧的世界观设定，包括时代背景、声音氛围、BGM风格建议、推荐历史人物清单。
项目名称：{project_title}
目标年龄段：{target_age}
历史时期：{historical_period}
主题方向：{theme}
</task>

<guidelines>
1. 时代背景描述要生动有趣，让小朋友一听就有画面感——多用颜色、声音、气味描写
2. 声音氛围要具体：清晨的鸟叫、集市的喧闹、远处的马蹄声、风吹竹简的沙沙声
3. BGM 风格建议要包含具体乐器（如古筝、笛、编钟）、节奏（舒缓/明快）、情绪色彩
4. historical_figures 必须是{historical_period}时期真实存在的历史或神话人物，优先选自封神演义
5. 所有内容适合3-10岁儿童，避免血腥、恐怖、成人化的描述
</guidelines>

<output>
请输出 JSON 格式：
{{"time_period": "朝代+具体时期（如商朝末年·纣王时期）", "location": "主要场景地点（2-3个具体地点，如朝歌城、渭水边、摘星楼）", "audio_atmosphere": "声音氛围描述（4-6句，包含具体声音细节）", "bgm_style": "乐器+节奏+情绪（如：古筝+编钟为主，节奏舒缓，带有神秘感和童趣）", "sound_effects": ["场景音效1", "场景音效2", "场景音效3", "场景音效4"], "historical_figures": ["推荐出场历史人物1", "推荐出场历史人物2", "推荐出场历史人物3"], "suggested_locations": ["建议场景地点1", "建议场景地点2", "建议场景地点3"]}}
</output>

<constraints>
✅ 所有内容必须基于{historical_period}的真实历史背景
✅ 历史人物必须是该时期真实存在或封神演义中的人物
✅ 语言适合3-10岁儿童理解和欣赏
❌ 禁止引入不符合历史时期的元素（如现代物品、后世人物）
❌ 禁止描述暴力、恐怖或令人不适的场景
❌ 禁止使用成人化的复杂概念
</constraints>"""
```

- [ ] **Step 2: Commit**

```
git add backend/app/services/prompt_service.py
git commit -m "feat: enhance PODCAST_WORLD template with input/constraints and expanded output fields"
```

---

### Task 2: 增强 PODCAST_OUTLINE 模板（核心）

**Files:**
- Modify: `backend/app/services/prompt_service.py:2579-2600`

**增强内容：** 从 22 行简略模板扩展为完整 RTCO 框架，新增 input/constraints 块和更多变量。

- [ ] **Step 1: 替换 PODCAST_OUTLINE 模板**

```python
PODCAST_OUTLINE = """<system>
你是儿童广播剧的编剧兼历史顾问，擅长将真实历史故事改编为有趣的穿越冒险剧集。你严格遵循历史事实和封神演义原著设定，绝不会编造不存在的历史人物或偏离世界观。每集5-8分钟，用"小朋友穿越到历史现场"的方式讲历史知识。
</system>

<task>
为《{project_title}》设计{chapter_count}集剧集大纲。每集5-8分钟，用"小朋友穿越到历史现场"的方式讲故事。
必须精确生成{chapter_count}集，不多不少。
</task>

<input>
【项目信息】
书名：{project_title}
主题：{theme}
历史时期：{historical_period}

【世界观设定】
地点：{location}
氛围：{atmosphere}
世界规则：{world_rules}
BGM风格：{bgm_style}

【主角团】
{main_characters}

【核心要求】
1. 所有出场历史人物必须来自封神演义或商朝末年真实历史
2. 主角团成员固定为已注册角色（见上方列表），禁止新增常驻成员
3. 每集只增加1个历史嘉宾角色（historical_figure 字段）
</input>

<guidelines>
1. 每集必须有一个清晰的历史知识点（knowledge_point：用一句话讲清一个历史概念）
2. 每集必须有穿越的趣味场景（character_focus：具体到某角色在历史场景中的体验）
3. 每集必须有角色互动亮点（和历史人物的对话碰撞）
4. 每集结尾必须有悬念钩子（cliffhanger：和下一集的历史人物/事件相关）
5. 情感曲线要有起伏（emotion：如"好奇→惊讶→恍然大悟"）
6. 预估时长5-8分钟（约1500-2500字）
7. 首集用于建立世界观、介绍主角团、展开第一次穿越
8. 后续剧集逐步深化历史知识、发展角色关系
</guidelines>

<output>
按以下 JSON 格式输出剧集列表（精确{chapter_count}个对象）：
[{{"episode_number": 1, "title": "剧集标题（有趣吸引小朋友）", "historical_period": "本集涉及的朝代和时期", "historical_figure": "本集出场的历史人物名字（必须来自封神演义或商朝真实历史）", "knowledge_point": "本集核心知识点（一句话）", "character_focus": "主角团角色在本集的亮点", "scenes": ["场景1描述", "场景2描述", "场景3描述", "场景4描述"], "emotion": "情感曲线", "cliffhanger": "结尾悬念钩子（引出下一集）", "bgm_style": "本集BGM风格建议", "estimated_duration": "预估时长"}}]
</output>

<constraints>
✅ 精确生成{chapter_count}集，JSON数组长度必须等于{chapter_count}
✅ historical_figure 必须是封神演义或商朝真实历史人物，禁止编造
✅ 每集角色只能使用已注册主角团 + 本集 historical_figure
✅ knowledge_point 必须准确反映真实历史知识
✅ scenes 每集至少3个场景
❌ 禁止创造主角团之外的新常驻原创角色
❌ 禁止将后世人物放入商朝时期
❌ 禁止 historical_figure 字段为空或填写模糊描述
❌ 禁止脱离{historical_period}的历史背景
❌ 禁止角色OOC（偏离其注册性格设定）
</constraints>"""
```

- [ ] **Step 2: Commit**

```
git add backend/app/services/prompt_service.py
git commit -m "feat: enhance PODCAST_OUTLINE with full RTCO framework and historical constraints"
```

---

### Task 3: 增强 PODCAST_EPISODE_FIRST 模板

**Files:**
- Modify: `backend/app/services/prompt_service.py:2603-2655`

**增强内容：** 补充 bgm_style/sound_effects 到 input 块，增加"避免说教"原则和角色 OOC 约束。

- [ ] **Step 1: 替换 PODCAST_EPISODE_FIRST 模板**

```python
PODCAST_EPISODE_FIRST = """<system>
你是儿童广播剧的剧本作家，使用"旁白叙述+角色对话"的广播剧格式创作内容。你的作品将在喜马拉雅等平台播放，听众是3-10岁的小朋友和他们的家长。你善于把历史知识自然地融入角色对话中，让小朋友在故事里学到知识，而不是被说教。
</system>

<task>
请创作《{project_title}》的第{episode_number}集：{episode_title}。
这是该系列的第一集，需要建立世界观、介绍主角团、展开第一次穿越冒险。
</task>

<input>
历史时期：{historical_period}
历史人物：{historical_figure}
知识点：{knowledge_point}
角色聚焦：{character_focus}
情感基调：{emotion}
目标字数：{target_word_count}字（对应{estimated_duration}时长）
BGM风格：{bgm_style}
环境音效参考：{sound_effects}

主角团：
{characters_info}

场景描述：
{scenes}
</input>

<guidelines>
1. 必须使用【角色名】格式标注每一段发言，包括【旁白】
2. 对话要生动有趣，每个角色都有鲜明的说话风格
3. 冯奇奇：好奇捣蛋，总问"为什么"
4. 五花：三句不离吃的，但关键时刻很靠谱
5. 布皮冻：说话像果冻一样Q弹，喜欢说"你猜怎么着"
6. 白木苏：温和有耐心，像讲故事的大哥哥
7. 肥笼：用"喵呜"和动作参与剧情
8. 历史人物说话要符合身份但有反差萌（比如姜子牙可以很幽默但很智慧）
9. 旁白语言要温暖有画面感，像睡前故事
10. 知识点通过角色对话和情节自然带出，不直接念百科、不说"小朋友们请注意这是知识点"
11. 结尾设置悬念，为下一集做铺垫
</guidelines>

<constraints>
- 总字数控制在{target_word_count}字以内
- 每段对话不超过50字（小朋友注意力）
- 必须有至少2个角色之间的互动对话
- 必须有一个让小朋友笑出声的桥段
- 知识点必须自然融入剧情，禁止生硬说教
- 禁止角色OOC（偏离其注册性格设定）
</constraints>

<output>
请直接按以下格式输出广播剧内容：

【旁白】（历史场景描述，温暖有画面感，融入{bgm_style}的氛围感）
【角色名1】（对话内容，动作描述用括号）
【角色名2】（对话内容）
【旁白】（转场叙述）
...
</output>"""
```

- [ ] **Step 2: Commit**

```
git add backend/app/services/prompt_service.py
git commit -m "feat: enhance PODCAST_EPISODE_FIRST with bgm/sfx context and anti-lecturing guidance"
```

---

### Task 4: 增强 PODCAST_CHARACTER 模板（批量模式）

**Files:**
- Modify: `backend/app/services/prompt_service.py:2664-2681`

**增强内容：** 从单个角色生成改为支持批量，注入世界观和历史上下文，添加 constraints 防幻觉。

- [ ] **Step 1: 替换 PODCAST_CHARACTER 模板**

```python
PODCAST_CHARACTER = """<system>
你是儿童广播剧的选角导演，精通历史又懂声音设计。你为广播剧设计声音辨识度极高、性格鲜明的角色。你严格区分主角团常驻成员和历史嘉宾角色，不会混淆或编造角色。
</system>

<task>
为广播剧《{project_title}》设计{count}个角色的详细设定，特别注重声音特征和口头禅。角色类型为：{character_type}。
</task>

<input>
【项目背景】
历史时期：{historical_period}
场景地点：{location}
氛围基调：{atmosphere}

【已注册角色（请勿重复）】
{existing_characters}

【主角团性格锚点（如涉及请严格遵守）】
- 冯奇奇：捣蛋鬼，好奇心爆棚，心思细腻，总问"为什么"
- 五花：小吃货，名字谐音五花肉，三句不离吃但关键时刻靠谱
- 布皮冻：Q弹捣蛋鬼，外表皮内心软，喜欢说"你猜怎么着"
- 白木苏：温和大哥哥，团队的保姆和智囊，负责救场和历史讲解
- 肥笼：贪吃宠物猫，行动矫健，用"喵呜"表达情绪
</input>

<guidelines>
1. 每个角色需要独特的说话方式和声音标签
2. 口头禅要简单好记，小朋友能记住（3-6个字最佳）
3. 声音描述要具体：用"清脆像铃铛"而不是"好听"
4. 如果是历史人物，要符合封神演义原著设定，但增加反差萌
5. 主角团角色严格按上方性格锚点设计，不可偏离
6. speaking_pattern 描述说话节奏、常用语气词、语速特点
</guidelines>

<output>
请输出 JSON 数组格式（{count}个对象）：
[{{"name": "角色名（中文，2-4字）", "age": "年龄或年龄段", "gender": "男/女", "personality": "性格描述（50-100字）", "voice_style": "声音质感（如清脆稚嫩/低沉威严/欢快跳跃）", "speaking_pattern": "说话节奏和习惯（如语速快/慢/喜欢拖长音/常带语气词）", "catchphrase": "口头禅（3-6字，适合儿童记忆）"}}]
</output>

<constraints>
✅ 名字必须是中文，2-4字，符合角色背景和时代
✅ 生成数量精确为{count}个
✅ 历史人物名字必须来自封神演义或{historical_period}真实历史
✅ 所有角色名必须在已注册角色列表中不存在
❌ 禁止编造不在封神演义或{historical_period}历史中的角色名
❌ 禁止使用现代名字或外国名字
❌ 禁止口头禅中出现不适合儿童的内容
❌ 禁止与已注册角色重名
</constraints>"""
```

- [ ] **Step 2: Commit**

```
git add backend/app/services/prompt_service.py
git commit -m "feat: enhance PODCAST_CHARACTER with batch mode, world context, and anti-hallucination constraints"
```

---

### Task 5: 增强 PODCAST_REGENERATE 模板

**Files:**
- Modify: `backend/app/services/prompt_service.py:2684-2686`

当前 PODCAST_REGENERATE 只是简单 replace 了 PODCAST_EPISODE_FIRST 的"请创作"为"根据以下反馈重新创作"，但没有注入 feedback 变量。需要改成独立模板。

- [ ] **Step 1: 修改 PODCAST_REGENERATE 为独立模板**

```python
PODCAST_REGENERATE = PODCAST_EPISODE_FIRST.replace(
    "请创作《{project_title}》的第{episode_number}集：{episode_title}。",
    "根据以下反馈重新创作《{project_title}》的第{episode_number}集：{episode_title}。"
).replace(
    "这是该系列的第一集，需要建立世界观、介绍主角团、展开第一次穿越冒险。",
    "这是该系列的第{episode_number}集。修改要求：{feedback}"
)
```

- [ ] **Step 2: Commit**

```
git add backend/app/services/prompt_service.py
git commit -m "feat: enhance PODCAST_REGENERATE with feedback variable injection"
```

---

### Task 6: 在 template_definitions 中注册 6 个播客模板

**Files:**
- Modify: `backend/app/services/prompt_service.py:3189`（在最后一个模板注册之后插入）

**当前状态：** 6 个 PODCAST_* 模板已作为类属性存在，但未在 `get_all_system_templates()` 的 `template_definitions` 字典中注册。

- [ ] **Step 1: 在 template_definitions 字典中添加播客模板注册**

在 `template_definitions` 字典的最后一个条目（`INSPIRATION_QUICK_COMPLETE`）之后，`}` 闭合之前，插入：

```python
"PODCAST_WORLD": {
    "name": "播客世界观",
    "category": "播客模式",
    "description": "为儿童广播剧设计世界观设定、声音氛围和BGM风格",
    "parameters": ["project_title", "target_age", "historical_period", "theme"]
},
"PODCAST_OUTLINE": {
    "name": "播客剧集大纲",
    "category": "播客模式",
    "description": "将历史故事改编为广播剧剧集大纲，每集5-8分钟",
    "parameters": ["project_title", "theme", "chapter_count", "historical_period", "location", "atmosphere", "world_rules", "bgm_style", "main_characters"]
},
"PODCAST_EPISODE_FIRST": {
    "name": "播客第1集",
    "category": "播客模式",
    "description": "生成广播剧第1集完整内容（含开场和角色引入）",
    "parameters": ["project_title", "episode_number", "episode_title", "historical_period", "historical_figure", "knowledge_point", "character_focus", "emotion", "target_word_count", "estimated_duration", "bgm_style", "sound_effects", "characters_info", "scenes"]
},
"PODCAST_EPISODE_NEXT": {
    "name": "播客后续集",
    "category": "播客模式",
    "description": "生成广播剧后续集内容（承接上集悬念）",
    "parameters": ["project_title", "episode_number", "episode_title", "historical_period", "historical_figure", "knowledge_point", "character_focus", "emotion", "target_word_count", "estimated_duration", "bgm_style", "sound_effects", "characters_info", "scenes", "prev_cliffhanger"]
},
"PODCAST_CHARACTER": {
    "name": "播客角色生成",
    "category": "播客模式",
    "description": "为广播剧设计角色（侧重声音特征和口头禅），支持批量生成",
    "parameters": ["project_title", "count", "character_type", "historical_period", "location", "atmosphere", "existing_characters"]
},
"PODCAST_REGENERATE": {
    "name": "播客重生成",
    "category": "播客模式",
    "description": "根据反馈重新生成广播剧内容",
    "parameters": ["project_title", "episode_number", "episode_title", "feedback", "historical_period", "historical_figure", "knowledge_point", "character_focus", "emotion", "target_word_count", "estimated_duration", "bgm_style", "sound_effects", "characters_info", "scenes"]
}
```

- [ ] **Step 2: Commit**

```
git add backend/app/services/prompt_service.py
git commit -m "feat: register 6 podcast templates in template_definitions"
```

---

### Task 7: 修复 outlines.py 播客大纲变量注入

**Files:**
- Modify: `backend/app/api/outlines.py:1729-1736`

**当前问题：** 只注入了 3 个变量。需要注入 9 个变量，从 project 和 world 数据中提取。

- [ ] **Step 1: 增强 podcast_outline_generator 的变量注入**

替换第 1729-1736 行的 format_prompt 调用：

```python
yield await tracker.preparing("准备播客大纲提示词...")
template = await PromptService.get_template("PODCAST_OUTLINE", user_id_for_mcp, db)

# 从 project 提取世界观数据
world_location = project.world_location or "商朝·朝歌城"
world_atmosphere = project.world_atmosphere or "神秘悠远、充满历史厚重感"
world_rules = project.world_rules or "穿越到封神演义世界，历史事件和神话交织"
theme = project.theme or f"{project.title}的穿越冒险"
# bgm_style 尽量从 world-building 结果中提取
bgm_style = "古筝+编钟，舒缓明快，童趣神秘"

prompt = PromptService.format_prompt(
    template,
    project_title=project.title,
    theme=theme,
    chapter_count=chapter_count,
    historical_period=project.world_time_period or "商朝末年",
    location=world_location,
    atmosphere=world_atmosphere,
    world_rules=world_rules,
    bgm_style=bgm_style,
    main_characters=characters_info or "冯奇奇（捣蛋好奇男主角）、五花（吃货女孩）、布皮冻（Q弹调皮男孩）、白木苏（温和保姆大哥哥）、肥笼（贪吃宠物猫）"
)
logger.info(f"播客大纲生成: project={project.title}, chapters={chapter_count}")
```

- [ ] **Step 2: Commit**

```
git add backend/app/api/outlines.py
git commit -m "feat: inject full world context into podcast outline generation"
```

---

### Task 8: 修复 wizard_stream.py 播客角色生成

**Files:**
- Modify: `backend/app/api/wizard_stream.py:588-732`（characters_generator 函数）

**当前问题：** 播客模式下仍然使用 `CHARACTERS_BATCH_GENERATION` 小说模板，没有切换到 `PODCAST_CHARACTER`。

- [ ] **Step 1: 在 characters_generator 中添加播客模式分支**

在 `characters_generator` 函数中，找到模板选择位置（约第 729 行），替换为：

```python
# 在 template = await PromptService.get_template(...) 之前添加分支
content_mode = data.get("content_mode", "novel")
project_obj_result = await db.execute(
    select(Project).where(Project.id == project_id)
)
project_obj = project_obj_result.scalar_one_or_none()

if content_mode == "podcast" and project_obj:
    # 播客模式：使用 PODCAST_CHARACTER 模板
    # 查询已注册角色
    existing_chars_result = await db.execute(
        select(Character).where(Character.project_id == project_id)
    )
    existing_chars = existing_chars_result.scalars().all()
    existing_names = ", ".join([c.name for c in existing_chars]) if existing_chars else "无"

    template = await PromptService.get_template("PODCAST_CHARACTER", user_id, db)
    base_prompt = PromptService.format_prompt(
        template,
        project_title=project.title,
        count=count,
        character_type="主角团+历史嘉宾",
        historical_period=project_obj.world_time_period or world_context.get("time_period", "商朝末年"),
        location=project_obj.world_location or world_context.get("location", "商朝·朝歌城"),
        atmosphere=project_obj.world_atmosphere or world_context.get("atmosphere", "神秘悠远"),
        existing_characters=existing_names,
    )
else:
    # 小说模式：保持原有逻辑
    template = await PromptService.get_template("CHARACTERS_BATCH_GENERATION", user_id, db)
    base_prompt = PromptService.format_prompt(
        template,
        # ... 原有参数保持不变 ...
    )
```

注意：播客模式的角色生成流程与小说不同——不需要职业体系分配和复杂的 relations 网络。播客模式生成的 JSON 格式也不同于小说模式。如果直接复用现有的批量分批逻辑可能会有兼容性问题。需要根据实际 `PODCAST_CHARACTER` 输出格式调整后续的解析和保存逻辑。

考虑到复杂性，如果当前 characters_generator 的架构难以同时支持两种模式，可以简化为：播客模式时跳过 wizard 的角色批量生成步骤，改在 outlines 生成后通过 auto_character_service 补全。

- [ ] **Step 2: Commit**

```
git add backend/app/api/wizard_stream.py
git commit -m "feat: add podcast character generation branch in wizard"
```

---

### Task 9: 修复 chapters.py 播客剧集变量注入

**Files:**
- Modify: `backend/app/api/chapters.py:1549-1564`

**当前问题：** `bgm_style` 和 `sound_effects` 未注入到 PODCAST_EPISODE_FIRST/NEXT 提示词中。

- [ ] **Step 1: 补充 bgm_style 和 sound_effects 变量**

替换第 1549-1564 行的 format_prompt 调用：

```python
base_prompt = PromptService.format_prompt(
    template,
    project_title=project.title,
    episode_number=current_chapter.chapter_number,
    episode_title=current_chapter.title or outline_data.get("title", f"第{current_chapter.chapter_number}集"),
    historical_period=historical_period,
    historical_figure=outline_data.get("historical_figure", ""),
    knowledge_point=outline_data.get("knowledge_point", ""),
    character_focus=outline_data.get("character_focus", ""),
    emotion=outline_data.get("emotion", "好奇"),
    target_word_count=target_word_count,
    estimated_duration=outline_data.get("estimated_duration", "6分钟"),
    bgm_style=outline_data.get("bgm_style", "古筝+编钟，舒缓明快"),
    sound_effects=", ".join(outline_data.get("sound_effects", [])) if outline_data.get("sound_effects") else "古代集市喧闹、风吹树叶、远处马蹄声",
    characters_info=podcast_characters_info or "暂无角色信息",
    scenes="\n".join(outline_data.get("scenes", [])) if outline_data.get("scenes") else "暂无场景描述",
    prev_cliffhanger="" if is_first else outline_data.get("cliffhanger", ""),
)
```

- [ ] **Step 2: Commit**

```
git add backend/app/api/chapters.py
git commit -m "feat: inject bgm_style and sound_effects into podcast episode generation"
```

---

### Task 10: 修复 auto_character_service.py 播客分支

**Files:**
- Modify: `backend/app/services/auto_character_service.py`

**当前问题：** `auto_character_service.py` 没有任何播客模式处理。大纲生成后自动补全角色时，使用的是小说模式的 `AUTO_CHARACTER_GENERATION` 模板。

- [ ] **Step 1: 在角色自动补全逻辑中添加播客模式分支**

找到 `_check_and_create_missing_characters_from_outlines` 或类似的自动角色补全函数，在使用 `AUTO_CHARACTER_GENERATION` 模板之前添加判断：

```python
# 获取项目信息
project_result = await db.execute(
    select(Project).where(Project.id == project_id)
)
project = project_result.scalar_one_or_none()

if project and project.content_mode == "podcast":
    # 播客模式：使用 PODCAST_CHARACTER 模板从大纲中提取历史人物创建角色
    template = await PromptService.get_template("PODCAST_CHARACTER", user_id, db)
    base_prompt = PromptService.format_prompt(
        template,
        project_title=project.title,
        count=len(missing_characters),
        character_type="历史嘉宾",
        historical_period=project.world_time_period or "商朝末年",
        location=project.world_location or "未设定",
        atmosphere=project.world_atmosphere or "未设定",
        existing_characters=", ".join([c.name for c in existing_characters]),
    )
else:
    # 小说模式：保持原有逻辑
    template = await PromptService.get_template("AUTO_CHARACTER_GENERATION", user_id, db)
    base_prompt = PromptService.format_prompt(
        template,
        # ... 原有参数 ...
    )
```

- [ ] **Step 2: Commit**

```
git add backend/app/services/auto_character_service.py
git commit -m "feat: add podcast mode branch to auto character service"
```

---

## 验证清单

- [ ] 创建播客项目 → 生成世界观 → 检查输出含 historical_figures 清单且都在封神演义范围内
- [ ] 生成播客大纲 → 检查所有 historical_figure 字段为真实历史/封神人物，无怪异名字
- [ ] 批量生成角色 → 名字正常、无重复、无非商朝人物、声音标签具体
- [ ] 生成一集播客内容 → 检查【角色名】格式、知识点自然融入、悬念钩子
- [ ] 自动角色补全 → 播客模式下使用 PODCAST_CHARACTER 而非小说模板
- [ ] 小说模式回归 → OUTLINE_CREATE / CHARACTERS_BATCH_GENERATION 不受影响
- [ ] template_definitions 包含 6 个 PODCAST_ 模板
