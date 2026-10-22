# 宿主 MCP、专业搜索技能与本地资料

本机调用目录快照日期为 2026-10-14。它记录工具可发现情况；除已明确标为实际内容读取的项目外，均不得据此声称搜索已成功。OpenCLI 每条只读命令见 [opencli-read-tools.json](opencli-read-tools.json)；当前宿主发现的搜索/读取 MCP 函数逐项见 [host-read-tools.md](host-read-tools.md)；平台职责见 [tool-routing.md](tool-routing.md)。

## 通用网页与页面读取

| 提供方 | 本机入口 | 负责内容 | 状态与边界 |
|---|---|---|---|
| 宿主网页搜索 | `mcp__codex_apps__search_service_web_run` 或当前宿主 web search tool | 单次网页发现、新闻、事实核对 | 当前会话工具已注册；按实际返回判断结果，不与 Exa 重复搜索 |
| Exa MCP | `mcporter call exa.web_search_exa/web_fetch_exa/web_search_advanced_exa/agent_run ...` | 网页搜索、已知页正文、过滤、多步研究 | 2026-10-14 `mcporter list exa --schema --all-parameters` 成功；官方搜索与官方正文抓取实测返回内容；`agent_run` 只确认工具已发现，此次未运行 |
| AnySearch | Skill 内 Node CLI：`node <anysearch-skill-dir>/scripts/anysearch_cli.js` | 垂直子域、结构化查询、并行查询、正文提取 | `runtime.conf` 已指向当前 LocalSkills 脚本；离线 `doc` 返回接口说明；本次在线查询遇 `api.anysearch.com` DNS 解析失败，实时检索待重试 |
| Skywork Search | `Skywork-Search` 技能的 `scripts/web_search.py` | Skywork 文档或 API 工作流所需资料 | `SKYWORK_API_KEY` 是其前置条件；无 Key 不当作已验证备用；用户请求搜索不触发自动密钥设置 |
| 页面读取 | Exa fetch；Jina Reader `curl https://r.jina.ai/URL`；AnySearch `extract URL` | 读取页面正文 | 优先已知 URL 的官方/平台读取；返回中须有实际正文 |
| 快速发现 | `agent-reach-search "query"` | 固定多源候选初筛 | 固定结果数且压缩渠道；只作初筛，随后按相关渠道补搜与深读 |

宿主网页工具和 Exa 是并列的普通网页入口：选择当前可实际调用且更适合问题的一种。需要特定过滤时选 Exa Advanced；多轮跨源研究才用 Exa Agent。AnySearch 专责垂直搜索，不统管所有网页检索。

## 宿主连接器与专用读工具

| 任务／连接器 | 可用入口 | 路由规则 |
|---|---|---|
| GitHub MCP | `mcp__codex_apps__github_search`、`github_search_repositories`、`github_search_issues`、`github_search_prs`、`github_search_commits`、`github_fetch_file/issue/issue_comments/pr` | 搜索和读取 public repo 资料；`gh` CLI 作备用；任何创建/评论/合并工具不纳入搜索路径 |
| Planner Core | `planner_status`、`planner_digest`、`planner_list`、`planner_get`、`planner_plan_preview` | 只查用户的 Planner 任务与规划，不作公网搜索；按任务状态/项目过滤，先读目录再读候选 |
| TickTick | `mcp__ticktick__search`、`search_task`、`fetch`、`get_project_with_undone_tasks` 等只读工具 | 用户问 TickTick 任务时查；写/完成/改期工具不得由搜索路由调用 |
| 本地 B站收藏 | `mcp__bili_reclass__bili_list_items` 或 `mcp__codex_apps__b__bili_list_items` | 查本地收藏目录；不等于站内全网视频搜索；同步为另一个操作 |
| NotebookLM | `search_notebooks`、`ask_question`、`get_notebook`、`list_notebooks` | 用户指定 NotebookLM 笔记本/来源时检索并回答；不是公网来源 |
| Basic Memory | `search`、`deep_search`、`search_notes`、`read_note` 等 | 用户指定个人知识库时搜索；不与项目文档或网络搜索混同 |
| AgentMemory／灵枢 | `memory_smart_search`、`memory_facet_query`、`mdcg_search`、`mdcg_recall` | 跨会话记忆只遵照本机 Memory ownership 和相关触发规则，不作为默认联网搜索 |
| 项目代码/文件 | `rg`、`rg --files`、`coding_tools2_search_text/read_file`、Codex `read_thread` | 当前工作区或用户明确提到的文件；旧 Codex 会话先 `read_thread` |
| Conversation Archive | `conversation_archive_search`、`deep_search` | 搜索用户明确指定的历史会话；保留日期、Agent 与命中上下文 |
| Deja | `recall`、`recall_context` | 只在用户明确问旧会话/先前修复，或排错需找缺失旧修复时调用 |
| 本地研究库 | `research-system` 的 `local_library.py search/open` | Fact 工作先查既有本地资料；联网证据另走外部渠道 |

连接器只列与搜索/读取相关的只读动作；通用 `execute`、写入、更新、删除、发送和评论能力不进入路由清单。每次根据工具 schema 与当前用户明确指定的资料范围调用。

## 专业技能入口

| 内容 | 入口与所有者 | 后续核验 |
|---|---|---|
| 学术文献／论文 | `academic-literature-search`；可用 OpenCLI arXiv/OpenAlex/PubMed/Crossref/知网/万方；明确 Semantic Scholar 引用问题选 Asta 专用技能 | 当前会话未注册 Asta MCP；学术聚合器记录的 `/Users/mac/Documents/local-deep-researcher` 目录不存在，不能走该脚本路线。使用实际可用原生源并报告覆盖 |
| 技能市场 | `unified-marketplace-search` 搜四源：LobeHub、SkillHub、skills.sh、本地 awesome-top-skills；指定 legacy 源才调 `skilldb-search` | 源失败逐源记录；市场结果用于找技能，不等于检索一般互联网 |
| 商品 | `buying-agent-cn` 决策；`cn-ecommerce-search-v2` 链接；`maishou` 纯价格；OpenCLI 淘宝/京东/亚马逊详情与评价 | 记录日期、SKU、价格来源；不同工具承担选购、商品发现、比价，避免同时重复跑完整流程 |
| 旅行与地点 | `domestic-travel-superplanner`；单查票务酒店用 `tripai-skill`；经纬度/POI/距离用 `maps` | 行程总规划与单个实时票务问题分开 |
| AI 新闻与行业讨论 | `aihot`（中文 AI 日报）；`ai-daily-digest`（订阅博客）；`last30days`（社交平台近 30 日） | 回到原始公告/帖子核对；专用技能的 setup、写入、成本规则仍适用 |
| Docs、云盘、日历 | 对应已连接 app 的 search/list/read 工具 | 仅用户指定账户/资料时搜索；外部搜索来源需独立引用 |
| 法规、软件包、模型、地图 | 对应 OpenCLI `gov-law/gov-policy/npm/nuget/pypi/dockerhub/hf/maps` 或专业技能 | 原始登记与版本、时间、地域需匹配问题 |

## 任一工具都要遵循的状态

`unavailable`（无程序或未配置）→ `discovered`（能列出/schema 可用）→ `search-returned`（查询返回内容）→ `content-read`（读到所需正文/评论/字幕）。只把最后适合的状态写成业务成功。渠道有明确分页时记录下一页/终页；仅 `limit` 输出截断不得推断平台已尽。
