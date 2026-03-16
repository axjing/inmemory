# 常驻记忆智能体

**一款基于llm 极速轻量版 构建的全天候 AI 记忆智能体**

大多数 AI 智能体都存在“失忆”问题。它们只在被调用时处理信息，之后便会彻底遗忘。本项目为智能体赋予**持久、可进化**的记忆能力，以轻量级后台进程**24 小时不间断运行**，持续对信息做处理、整合与关联。

无需向量数据库，无需嵌入向量。只靠一个大模型，就能读取、思考并写入结构化记忆。支持中英文等多种语言。

## 现存问题

当前主流的 LLM 记忆方案都有明显短板：

| 方案 | 缺陷 |
|---|---|
| **向量数据库 + RAG** | 被动式：只做一次嵌入，之后被动检索，无主动加工 |
| **对话摘要** | 时间久了会丢失细节，无法做跨内容关联 |
| **知识图谱** | 构建和维护成本太高 |

核心缺口：**没有一套系统能像人脑一样主动整合信息**。人类不只是存储记忆，睡眠时大脑还会回放、关联、压缩信息。这个智能体就是在模拟这件事。

## 架构

![架构图](./assets/architecture.png)

```plaintext
                              +---------------------------+
                              | Memory Orchestrator       |
                              | (Root Agent)              |
                              +---------------------------+
                               /           |           \
                              /            |            \
                             v             v             v
+---------------------------+  +---------------------------+  +---------------------------+
| Ingest Agent             |  | Consolidate Agent         |  | Query Agent               |
| • Summarize              |  | • Find patterns           |  | • Search memories         |
| • Extract entities       |  | • Merge related memories  |  | • Synthesize answers      |
| • Tag topics             |  |                           |  |                           |
+---------------------------+  +---------------------------+  +---------------------------+
           |                          |                          |
           |                          |                          |
           v                          v                          v
                              +---------------------------+
                              | SQLite DB                  |
                              | (memory.db)                |
                              +---------------------------+
```

每个智能体都有自己读写记忆库的工具，调度器会把请求路由给对应的专用智能体。

## 工作原理

### 1. 信息摄入（IngestAgent）

向智能体输入**任意文件**——文本、图片、音频、视频、PDF 均可。**摄入智能体（IngestAgent）** 借助 Gemini/OpenAI/Qwen等有关模型的多模态能力，从所有文件中提取结构化信息：

```
输入："Anthropic 报告称 Claude 62% 的使用场景与代码相关。
        AI 智能体是增长最快的品类。"
           │
           ▼
   ┌─────────────────────────────────────────────┐
   │ 摘要：Anthropic 报告 Claude 62% 用量与代码相关……  │
   │ 实体：[Anthropic, Claude, AI 智能体]            │
   │ 主题：[AI, 代码生成, 智能体]                    │
   │ 重要度：0.8                                   │
   └─────────────────────────────────────────────┘
```

**支持文件类型（共 27 种）：**

| 类别 | 后缀 |
|---|---|
| 文本 | `.txt`, `.md`, `.json`, `.csv`, `.log`, `.xml`, `.yaml`, `.yml` |
| 图片 | `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`, `.bmp`, `.svg` |
| 音频 | `.mp3`, `.wav`, `.ogg`, `.flac`, `.m4a`, `.aac` |
| 视频 | `.mp4`, `.webm`, `.mov`, `.avi`, `.mkv` |
| 文档 | `.pdf` |

**三种摄入方式：**

- **文件监听**：把支持的文件丢进 `./inbox` 文件夹，智能体自动处理
- **仪表板上传**：在 Streamlit 面板里点 📎 上传按钮
- **HTTP API**：`POST /ingest` 传入文本

**System Prompt:**

```python
system_prompt=(
            "You are a Memory Ingest Agent. You handle ALL types of input — text, images,\n"
            "audio, video, and PDFs. For any input you receive:\n"
            "1. Thoroughly describe what the content contains\n"
            "2. Create a concise 1-2 sentence summary\n"
            "3. Extract key entities (people, companies, products, concepts, objects, locations)\n"
            "4. Assign 2-4 topic tags\n"
            "5. Rate importance from 0.0 to 1.0\n"
            "6. Call store_memory with all extracted information\n\n"
            "For images: describe the scene, objects, text, people, and any visual details.\n"
            "For audio/video: describe the spoken content, sounds, scenes, and key moments.\n"
            "For PDFs: extract and summarize the document content.\n\n"
            "Use the full description as raw_text in store_memory so the context is preserved.\n"
            "Always call store_memory. Be concise and accurate.\n"
            "After storing, confirm what was stored in one sentence."
        )
```

**IngestAgent 可调用的工具**

- store_memory：将处理后的记忆存储在数据库中。
  - 参数：
    - raw_text：原始输入文本。
    - summary：简洁的1-2句话摘要。
    - entities：关键人物、公司、产品或概念。
    - topics：2-4个主题标签。
    - importance：表示重要性的0.0到1.0之间的浮点数。
    - source：该记忆的来源（文件名、URL等）。

  - 返回：
    - 包含memory_id和确认信息的字典。

### 2. 记忆整合（ConsolidateAgent）

**整合智能体（ConsolidateAgent）** 定时运行（默认：每 30 分钟）。就像人脑在睡眠时做的事，它会：

- 梳理未整合的记忆
- 找到它们之间的关联
- 生成跨主题洞察
- 压缩合并相关信息

```
记忆 #1："AI 智能体增长很快，但可靠性是难题"
记忆 #2："Q1 重点：把推理成本降 40%"
记忆 #3："现有 LLM 记忆方案都有缺陷"
记忆 #4："智能收件箱思路：给邮件做持久 AI 记忆"
                   │
                   ▼ 整合智能体
   ┌─────────────────────────────────────────────┐
   │ 关联关系：                                   │
   │   #1 ↔ #3：智能体可靠性需要更好的记忆架构      │
   │   #2 ↔ #1：降本才能规模化部署智能体            │
   │   #3 ↔ #4：智能收件箱是重构式记忆的一种应用     │
   │                                             │
   │ 洞察："下一代 AI 工具的瓶颈，在于从静态 RAG    │
   │ 转向动态记忆系统"                             │
   └─────────────────────────────────────────────┘
```

**System Prompt:**

```python
system_prompt=(
            "You are a Memory Consolidation Agent. You:\n"
            "1. Call read_unconsolidated_memories to see what needs processing\n"
            "2. If fewer than 2 memories, say nothing to consolidate\n"
            "3. Find connections and patterns across the memories\n"
            "4. Create a synthesized summary and one key insight\n"
            "5. Call store_consolidation with source_ids, summary, insight, and connections\n\n"
            "Connections: list of dicts with 'from_id', 'to_id', 'relationship' keys.\n"
            "Think deeply about cross-cutting patterns."
        )
```

**ConsolidateAgent 可调用的工具**

- read_unconsolidated_memories：读取尚未巩固的记忆。返回：包含未巩固记忆列表和计数的字典。
- store_consolidation：存储整合结果，并将源记忆标记为已整合。
  - 参数：
    - source_ids：已整合的记忆ID列表。
    - summary：所有源记忆的综合摘要。
    - insight：发现的一个关键模式或见解。
    - connections：包含“from_id”、“to_id”、“relationship”的字典列表。

  - 返回：
    - 带有确认信息的字典。

### 3. 记忆查询(QueryAgent)

提出任何问题，**查询智能体（QueryAgent）** 都会读取全部记忆和整合洞察，并带上来源引用给出答案：

```
问："我该重点关注什么？"

答："根据你的记忆，优先做：
   1. 3 月 15 日前上线 API [记忆 2]
   2. 智能体可靠性问题 [记忆 1] 可以用重构式记忆解决 [记忆 3]
   3. 智能收件箱思路 [记忆 4] 验证了持久 AI 记忆的市场需求"
```

**System Prompt:**

```python
system_prompt=(
            "You are a Memory Query Agent. When asked a question:\n"
            "1. Call read_all_memories to access the memory store\n"
            "2. Call read_consolidation_history for higher-level insights\n"
            "3. Synthesize an answer based ONLY on stored memories\n"
            "4. Reference memory IDs: [Memory 1], [Memory 2], etc.\n"
            "5. If no relevant memories exist, say so honestly\n\n"
            "Be thorough but concise. Always cite sources."
        )
```

**QueryAgent 可调用的工具**

- read_all_memories:从数据库中读取所有存储的记忆，按最新的在前排序。返回：包含记忆列表和计数的字典。
- read_consolidation_history:读取过往的整合见解。返回：包含整合记录列表的字典。

### 4. 记忆协调器(Memory orchestrator)

OrchestratorAgent是主智能体，将记忆操作路由到专业Agent。负责协调其他Agent(IngestAgent, ConsolidateAgent, QueryAgent)的工作。

**System Prompt:**

```python
system_prompt=(
            "You are the Memory Orchestrator for an always-on memory system.\n"
            "Route requests to the right sub-agent:\n"
            "- New information -> ingest_agent\n"
            "- Consolidation request -> consolidate_agent\n"
            "- Questions -> query_agent\n"
            "- Status check -> call get_memory_stats and report\n\n"
            "After the sub-agent completes, give a brief summary."
        )
```

**OrchestratorAgent 可调用的子智能体**

- IngestAgent: 处理新信息的摄入
- ConsolidateAgent: 执行记忆整合
- QueryAgent: 处理查询请求

**OrchestratorAgent 可调用的工具**

- get_memory_stats：获取当前内存统计信息。返回：包含内存、整合等计数的字典。

## 快速上手

### 1. 安装

```bash
pip install -r requirements.txt
```

### 2. 设置 API 密钥

### 3. 启动智能体

```bash
python agent.py
```

完成。智能体已后台运行：

- 监听 `./inbox/` 里的新文件（文本、图片、音频、视频、PDF）
- 每 30 分钟自动整合一次
- 在 `http://localhost:8888` 提供查询接口

### 4. 投喂信息

**方式 A：丢文件**

```bash
echo "一些重要信息" > inbox/notes.txt
cp photo.jpg inbox/
cp meeting.mp3 inbox/
cp report.pdf inbox/
# 智能体会在 5–10 秒内自动摄入
```

**方式 B：HTTP API**

```bash
curl -X POST http://localhost:8888/ingest \
  -H "Content-Type: application/json" \
  -d '{"text": "AI 智能体是未来", "source": "article"}'
```

### 5. 查询

```bash
curl "http://localhost:8888/query?q=你知道些什么"
```

### 6. 可视化面板（可选）

```bash
streamlit run dashboard.py
# 打开 http://localhost:8501
```

Gradio 面板连接正在运行的智能体，提供可视化操作：

- **摄入**：文本输入、文件上传（图/音/视频/PDF）
- **查询**：自然语言查记忆
- **浏览 / 删除** 记忆
- **手动触发**记忆整合

## API 文档

| 接口 | 方法 | 说明 |
|---|---|
| `/status` | GET | 记忆统计（数量） |
| `/memories` | GET | 列出所有记忆 |
| `/ingest` | POST | 摄入文本（`{"text": "...", "source": "..."}`） |
| `/query?q=...` | GET | 自然语言查询记忆 |
| `/consolidate` | POST | 手动触发整合 |
| `/delete` | POST | 删除单条记忆（`{"memory_id": 1}`） |
| `/clear` | POST | 清空所有记忆（完全重置） |

## 命令行参数

```bash
python agent.py [选项]

  --watch DIR              监听目录（默认：./inbox）
  --port PORT              API 端口（默认：8888）
  --consolidate-every MIN  整合间隔（默认：30 分钟）
```

## 项目结构

```
.
├── agent.py          # 常驻 ADK 智能体（核心）
├── dashboard.py      # Gradio 面板（连接 API）
├── requirements.txt  # 依赖
├── inbox/            # 自动监听目录
├── docs/             # 图片资源
├── llms/             # llm 客户端实现（多提供商、多模型支持；支持多模态、流式传输、异步调用、调用工具等）
├── ...
└── memory.db         # sqlite3记忆库（自动生成）
```

## 技术栈

- 任何支持OpenAI API、Gemini API、Claude API等接口的模型切换
- SQLite：持久化记忆存储
- aiohttp：HTTP API异步通信
- gradio：可视化面板

### requirements.txt

```
gradio
openai
google-genai
google-adk
requests
aiohttp
sqlite3
python-dotenv
pydantic
...
```
