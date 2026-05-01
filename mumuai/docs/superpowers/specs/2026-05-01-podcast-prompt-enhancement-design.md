# 播客提示词全面增强 — 设计文档

> 日期: 2026-05-01 | 版本: v1.0 | 状态: 待实施

---

## 一、问题诊断

2026-04-30 测试发现播客大纲和角色生成效果差，AI 创造了不符合封神榜/商朝背景的现代角色和怪异名字。

根因分析：播客提示词模板变量注入严重不足。

| 指标 | 小说模式 OUTLINE_CREATE | 播客模式 PODCAST_OUTLINE |
|------|------------------------|--------------------------|
| 注入变量数 | 15+ | 3 |
| 世界观数据 | ✅ time_period, location, atmosphere, rules | ❌ 仅 historical_period |
| 角色信息 | ✅ 全量性格+背景 | ❌ 仅名称列表（可能为空回退硬编码） |
| 主题/主线 | ✅ theme | ❌ 缺失 |
| 章节数量 | ✅ chapter_count | ❌ 缺失 |
| constraints 块 | ✅ 详细 ✅/❌ 清单 | ❌ 缺失 |

连锁问题：PODCAST_CHARACTER 同样缺少世界观和历史上下文，无法约束角色生成范围。

---

## 二、改动范围

### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/services/prompt_service.py` | 6 个 PODCAST_* 模板全部增强 |
| `backend/app/api/outlines.py` | 播客大纲分支注入完整上下文变量 |
| `backend/app/api/wizard_stream.py` | 播客角色生成切换增强模板 + 批量模式 |
| `backend/app/api/chapters.py` | 播客剧集分支变量补充 |
| `backend/app/services/auto_character_service.py` | 新增播客模式分支 |

### 不涉及

- 数据库迁移（无 schema 变更）
- 前端改动
- 音频生成流水线

---

## 三、模板增强设计

### 3.1 PODCAST_WORLD（世界观生成）

**当前问题**：无 constraints 块，输出字段粗糙。

**增强内容**：
- 新增 `<input>` 块，注入项目标题、主题、目标年龄
- `<guidelines>` 扩展：增加感官细节（听觉/视觉/嗅觉）
- `<output>` 扩展：增加 `historical_figures` 预选清单、`suggested_locations` 列表
- 新增 `<constraints>` 块：禁止暴力/恐怖、禁止脱离历史时期

**变量**：project_title, target_age, historical_period, theme

---

### 3.2 PODCAST_OUTLINE（剧集大纲生成）★ 核心

**当前问题**：仅 3 个变量，缺乏世界观/角色详情/主题/剧集数量约束。

**增强内容**：
- `<system>` 增强：强调"历史顾问+儿童编剧"双重身份
- `<task>` 明确：剧集数量 `{chapter_count}`、主线任务
- 新增 `<input>` 块：注入世界观全量数据、角色性格详情、主题主线、bgm_style
- `<guidelines>` 扩展：每集结构模板（穿越→探索→知识点→冲突→悬念钩子）
- `<output>` 保持 JSON 数组格式，增加字段约束说明
- 新增 `<constraints>` 块：
  - ✅ historical_figure 必须是真实历史/封神演义人物
  - ✅ 角色只能使用已注册角色 + 本集 historical_figure
  - ❌ 禁止创建主角团之外的新原创角色
  - ❌ 禁止偏离商朝/封神演义世界观
  - ❌ 禁止 historical_figure 为空

**变量注入补全（outlines.py）**：

```python
PromptService.format_prompt(
    template,
    project_title=project.title,
    theme=project.theme,                    # 新增
    chapter_count=chapter_count,            # 新增（之前完全缺失）
    historical_period=project.world_time_period,
    location=project.world_location,        # 新增
    atmosphere=project.world_atmosphere,    # 新增
    world_rules=project.world_rules,        # 新增
    main_characters=characters_info,        # 已有但格式需增强
    bgm_style=bgm_style,                    # 新增（从世界观取）
)
```

---

### 3.3 PODCAST_EPISODE_FIRST / PODCAST_EPISODE_NEXT（剧集内容生成）

**当前问题**：相对完整，但缺少 bgm_style / sound_effects 上下文，guidelines 偏重角色说话风格而非内容质量。

**增强内容**：
- `<input>` 补充 `bgm_style` 和 `sound_effects`（从世界观来）
- `<guidelines>` 增加"避免说教"原则：知识点通过角色对话自然带出
- `<constraints>` 新增：
  - ✅ 每集有且仅有一个知识点的自然呈现
  - ✅ 结尾钩子必须和下一集历史人物/知识点相关
  - ❌ 角色 OOC（如冯奇奇突然变沉稳）
  - ❌ 超过 `{target_word_count}` 字

**变量补充（chapters.py）**：

```python
# 新增
bgm_style=outline_data.get("bgm_style", ""),
sound_effects=", ".join(outline_data.get("sound_effects", [])),
```

---

### 3.4 PODCAST_CHARACTER（角色生成）★ 重点

**当前问题**：只生成单个角色，无世界观/历史上下文，无 constraints。

**增强内容**：
- `<system>` 增强："儿童广播剧选角导演"，懂历史+懂声音设计
- `<task>` 明确：生成 `{count}` 个角色，指定类型（主角团 / 历史嘉宾）
- 新增 `<input>` 块：注入世界观、历史时期、已注册角色名列表（防重复）
- `<guidelines>`：
  1. 主角团性格锚定（冯奇奇=捣蛋好奇、五花=吃货、布皮冻=Q弹捣蛋、白木苏=温和保姆、肥笼=贪吃猫）
  2. 历史人物符合封神演义原著设定但有反差萌
  3. 声音标签具体化："清脆像铃铛" > "好听"
- `<output>` 改为 JSON 数组格式（支持批量）
- 新增 `<constraints>` 块：
  - ✅ 名字必须中文，符合角色背景
  - ❌ 禁止编造不在封神演义中的历史人物名
  - ❌ 禁止与已注册角色重名

**变量**：project_title, count, historical_period, location, atmosphere, existing_characters, character_type

---

### 3.5 PODCAST_REGENERATE（重新生成）

**改动最小**：在 PODCAST_EPISODE_FIRST 基础上补充 `{feedback}` 变量和约束块。

---

### 3.6 角色自动补全（auto_character_service.py）

**当前状态**：使用 `AUTO_CHARACTER_GENERATION` 模板（小说模式），无播客分支。

**新增**：播客模式下使用 `PODCAST_CHARACTER` 模板，注入世界观和历史时期上下文。

---

## 四、调用点变量注入对照表

| 调用点 | 文件 | 当前变量数 | 修复后 | 新增变量 |
|--------|------|-----------|--------|----------|
| 世界观生成 | wizard_stream.py | 3 | 4 | theme |
| 大纲生成 | outlines.py | 3 | 9 | theme, chapter_count, location, atmosphere, world_rules, bgm_style |
| 角色批量生成 | wizard_stream.py | 1 | 7 | count, historical_period, location, atmosphere, existing_characters, character_type |
| 剧集第1集 | chapters.py | 11 | 13 | bgm_style, sound_effects |
| 剧集后续集 | chapters.py | 12 | 14 | bgm_style, sound_effects |
| 角色自动补全 | auto_character_service.py | - | 6 | 新增播客分支 |

---

## 五、核心设计原则

> **让 AI 知道的越多，它编的越少。**

所有增强围绕三个目标：
1. **历史围栏**：通过 historical_period + world_rules + historical_figures 清单锁定人物范围
2. **角色锚定**：主角团性格在提示词中硬编码，避免 AI 漂移
3. **结构约束**：每个模板补全 RTCO 框架（system/task/input/guidelines/output/constraints）

---

## 六、验证方案

1. 创建播客项目 → 生成世界观 → 检查 historical_figures 清单是否在封神演义范围内
2. 生成播客大纲 → 检查所有 historical_figure 字段是否真实人物
3. 批量生成角色 → 检查名字无怪异、无重复、无非商朝人物
4. 生成一集内容 → 检查【角色名】格式、知识点自然度、悬念钩子
5. 小说模式回归测试 → 确认 OUTLINE_CREATE 等不受影响
