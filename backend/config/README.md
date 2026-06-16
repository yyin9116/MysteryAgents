# Prompt 配置文件说明

## 概述

`prompts.yaml` 文件允许你自定义游戏中 AI Agent 的 prompt，而无需修改代码。

## 工作原理

1. **配置文件优先**：如果 `backend/config/prompts.yaml` 存在，系统会使用其中的 prompt 模板
2. **硬编码后备**：如果配置文件不存在或加载失败，系统会使用代码中的硬编码默认值
3. **热加载**：修改配置文件后，重启游戏服务即可生效（无需重新部署）

## 配置文件结构

```yaml
# 描述阶段 Prompt 模板
description_prompt: |
  你的 prompt 内容...
  可以使用以下变量：
  - {agent_name}: Agent 名字
  - {mbti_type}: MBTI 类型
  - {iq_level}: IQ 等级
  - {word}: Agent 的词
  - {other_agents_list}: 其他玩家列表
  - {personality_traits}: 性格特征
  - {speaking_style}: 说话风格
  - {thinking_pattern}: 思维模式

# 投票阶段 Prompt 模板
voting_prompt: |
  你的 prompt 内容...
  可以使用以下变量：
  - {agent_name}: Agent 名字
  - {mbti_type}: MBTI 类型
  - {iq_level}: IQ 等级
  - {word}: Agent 的词
  - {other_agents_list}: 可投票的玩家列表
```

## 可用变量

### 描述阶段 (description_prompt)

| 变量 | 说明 | 示例 |
|------|------|------|
| `{agent_name}` | Agent 的名字 | "小明" |
| `{mbti_type}` | MBTI 人格类型 | "ENTJ" |
| `{iq_level}` | IQ 等级 | "High" / "Mid" / "Low" |
| `{word}` | Agent 的词 | "牛奶" |
| `{other_agents_list}` | 其他存活玩家列表 | "- agent_2: 小红\n- agent_3: 小刚" |
| `{personality_traits}` | 性格特征描述 | "果断、理性、善于规划..." |
| `{speaking_style}` | 说话风格描述 | "直接、简洁、有条理..." |
| `{thinking_pattern}` | 思维模式描述 | "逻辑分析、战略思考..." |

### 投票阶段 (voting_prompt)

| 变量 | 说明 | 示例 |
|------|------|------|
| `{agent_name}` | Agent 的名字 | "小明" |
| `{mbti_type}` | MBTI 人格类型 | "ENTJ" |
| `{iq_level}` | IQ 等级 | "High" / "Mid" / "Low" |
| `{word}` | Agent 的词 | "牛奶" |
| `{other_agents_list}` | 可投票的玩家列表 | "- agent_2: 小红\n- agent_3: 小刚" |

## 使用示例

### 1. 简化版 Prompt

如果你想让 Agent 的发言更简洁：

```yaml
description_prompt: |
  你是 {agent_name}，MBTI 类型是 {mbti_type}。
  你的词是：{word}
  
  规则：
  1. 不能直接说出词本身
  2. 不能说出词中的任何字
  3. 用其他方式描述这个词
  
  输出 JSON 格式：
  {{
    "thought": "你的思考",
    "speech": "你的描述（一句话）",
    "suspicion": {{"agent_id": 分数}}
  }}
```

### 2. 增强版 Prompt

如果你想让 Agent 更有创意：

```yaml
description_prompt: |
  # 创意描述挑战
  
  你是 {agent_name}，一个富有创造力的玩家。
  你的词是：{word}
  
  ## 挑战目标
  1. 用最独特的角度描述你的词
  2. 避免使用常见的描述（颜色、形状等）
  3. 尝试用比喻、联想、情感等方式
  
  ## 其他玩家
  {other_agents_list}
  
  ## 输出格式
  {{
    "thought": "我的创意思路...",
    "speech": "我的独特描述",
    "suspicion": {{"agent_id": 分数}}
  }}
```

### 3. 角色扮演版 Prompt

如果你想让 Agent 更有个性：

```yaml
description_prompt: |
  你是 {agent_name}，一个 {mbti_type} 类型的玩家。
  
  ## 你的性格
  {personality_traits}
  
  ## 你的说话风格
  {speaking_style}
  
  ## 你的词
  {word}（记住：不能直接说出来！）
  
  ## 任务
  用符合你性格的方式描述你的词，让队友能猜到，但不要太明显。
  
  输出 JSON：
  {{
    "thought": "符合 {mbti_type} 性格的思考过程",
    "speech": "符合你说话风格的描述",
    "suspicion": {{"agent_id": 分数}}
  }}
```

## 注意事项

### 1. YAML 格式

- 使用 `|` 表示多行文本
- 注意缩进（使用空格，不要用 Tab）
- 变量使用 `{variable_name}` 格式

### 2. 变量替换

- 所有变量必须用花括号包裹：`{agent_name}`
- 如果 prompt 中需要使用花括号，需要双写：`{{` 和 `}}`
- 示例：JSON 格式需要写成 `{{"key": "value"}}`

### 3. 测试 Prompt

修改 prompt 后，建议：
1. 重启游戏服务
2. 开始一局新游戏
3. 观察 Agent 的发言是否符合预期
4. 查看日志确认是否使用了配置文件

### 4. 日志信息

启动游戏时，日志会显示：
- ✅ `已从配置文件加载 prompt 模板` - 成功加载配置文件
- ℹ️ `未找到 prompt 配置文件，使用硬编码默认值` - 使用默认 prompt
- ⚠️ `加载 prompt 配置文件失败，使用硬编码默认值` - 配置文件有错误

## 高级用法

### 1. 条件性 Prompt

你可以在 prompt 中根据 IQ 等级给出不同的指导：

```yaml
description_prompt: |
  你是 {agent_name}，IQ 等级：{iq_level}
  
  {% if iq_level == "High" %}
  ## 高智商策略
  - 使用复杂的逻辑分析
  - 提供多层次的描述
  - 考虑心理战术
  {% elif iq_level == "Mid" %}
  ## 中等智商策略
  - 使用直接的描述
  - 保持逻辑清晰
  {% else %}
  ## 低智商策略
  - 简单直接
  - 可能犯些小错误
  {% endif %}
```

注意：当前版本不支持条件语句，这只是示例。如需实现，需要修改代码使用 Jinja2 模板引擎。

### 2. 多语言支持

你可以创建不同语言的配置文件：

- `prompts.yaml` - 默认（中文）
- `prompts_en.yaml` - 英文版
- `prompts_ja.yaml` - 日文版

然后在代码中根据用户语言选择加载不同的文件。

## 故障排除

### 问题：配置文件不生效

**解决方案**：
1. 检查文件路径是否正确：`backend/config/prompts.yaml`
2. 检查 YAML 格式是否正确（使用在线 YAML 验证器）
3. 检查日志中是否有错误信息
4. 确保重启了游戏服务

### 问题：变量没有被替换

**解决方案**：
1. 检查变量名是否正确（区分大小写）
2. 确保使用了花括号：`{variable_name}`
3. 检查是否有拼写错误

### 问题：JSON 格式错误

**解决方案**：
1. 在 prompt 中的 JSON 示例，花括号需要双写：`{{"key": "value"}}`
2. 确保 prompt 中明确要求输出 JSON 格式
3. 提供清晰的 JSON 示例

## 最佳实践

1. **保留默认值**：修改前先备份原始的 `prompts.yaml`
2. **渐进式修改**：一次只修改一小部分，测试后再继续
3. **版本控制**：将 `prompts.yaml` 加入 Git，方便回滚
4. **文档化**：在 prompt 中添加注释说明你的修改意图
5. **测试充分**：在不同场景下测试（不同 MBTI、不同 IQ、不同轮次）

## 示例场景

### 场景 1：教育模式

让 Agent 更注重解释和教学：

```yaml
description_prompt: |
  你是一个教育者，需要帮助其他玩家理解游戏。
  你的词是：{word}
  
  在描述时：
  1. 解释你的思考过程
  2. 给出清晰的线索
  3. 帮助队友理解游戏规则
```

### 场景 2：竞技模式

让 Agent 更具竞争性：

```yaml
description_prompt: |
  你是一个竞技玩家，目标是赢得游戏。
  你的词是：{word}
  
  策略：
  1. 分析对手的弱点
  2. 使用心理战术
  3. 隐藏你的真实意图
```

### 场景 3：娱乐模式

让 Agent 更有趣：

```yaml
description_prompt: |
  你是一个幽默的玩家，让游戏更有趣。
  你的词是：{word}
  
  风格：
  1. 使用幽默的描述
  2. 制造有趣的误导
  3. 让游戏充满欢乐
```

## 技术细节

### 加载流程

1. 游戏服务初始化时调用 `_load_prompt_templates()`
2. 检查 `backend/config/prompts.yaml` 是否存在
3. 如果存在，使用 `yaml.safe_load()` 加载
4. 将模板缓存在类变量 `_prompt_templates` 中
5. 生成 prompt 时，优先使用配置文件，否则使用硬编码默认值

### 性能优化

- 配置文件只在首次初始化时加载一次
- 使用类级别缓存，避免重复读取文件
- 模板变量替换使用 Python 的 `str.format()` 方法，性能高效

## 相关文件

- `backend/services/game_service.py` - 主要实现代码
- `backend/config/prompts.yaml` - 配置文件
- `backend/requirements.txt` - 依赖（包含 pyyaml）

## 更新日志

- 2024-12-23: 初始版本，支持描述和投票阶段 prompt 配置
