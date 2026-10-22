# 搜索工具与渠道路由

本页定义首选路由和备用关系。逐项 OpenCLI 只读能力见 [opencli-read-tools.json](opencli-read-tools.json)；宿主 MCP 与专用技能见 [host-tools.md](host-tools.md)。OpenCLI 清单只是能力快照，不是路由授权；**小红书强制 `xhs-cli + xhs-comments`，禁止 OpenCLI，包括通用 browser 与失败回退**。渠道固定规则优先于本页通用备用建议。只把实际搜索或内容读取能力用于证据，账号状态、心跳、登录页、工具列表不算搜索结果。

## 按任务选工具

| 任务 | 首选 | 备用或加验 |
|---|---|---|
| 单个当前事实、新闻、站点发现 | 可用的宿主网页搜索；本机经实测可用的 Exa `web_search_exa` | Skywork Search（有 Key 时）或 Google/Brave/DuckDuckGo/Yahoo OpenCLI；用另一引擎补查时保留独立来源 |
| 查一个已知 URL | Exa `web_fetch_exa` 或专用官方读取器 | Jina Reader；AnySearch `extract` |
| 找现成工具或跨方案比较 | Exa `web_search_exa`；跨多个条件才选 `agent_run` | GitHub 仓库/Release/Issue、官方文档、用户反馈分渠道核查 |
| 指定网站、日期、类别或地区 | Exa `web_search_advanced_exa`，只传实时 schema 支持的字段 | AnySearch 对应垂直子域；原生 API |
| 专业垂直数据 | 对应专业技能或原生平台（学术、金融、旅行、商品、包仓库等） | AnySearch：先 `get_sub_domains`，再按其 required 参数查询；通用引擎用于补发现 |
| 近期真实使用意见／热点 | 指定社区原生搜索；跨社区过去 30 天才调用 `last30days` | 评论、回复、Issue 分别读；Exa 站内检索必须标为间接 |
| 视频、播客内容 | 对应平台搜索与元数据 | 对应字幕/转录、评论工具；标题不算内容已读 |
| 用户个人资料、旧聊天、本地资料 | 用户点名的连接器、档案搜索、本地知识库 | 联网搜索不得代替私有来源；Deja 仅限用户明确问旧会话或缺失的旧修复 |
| 仅需发现候选 | `agent-reach-search` | 后续改用各渠道原生搜索和正文读取；该快捷入口永不代表全量覆盖 |

宿主网页搜索、Exa、AnySearch、Skywork 都能做普通网页检索，职责按上表固定：宿主/Exa 负责普通发现，AnySearch 负责先探测子域的垂直查询，Skywork 是依赖 Key 的补充或文档工作流检索。每个子问题先选一个主引擎；只有缺少来源、要验证分歧或任务明确要求多源时才增加独立引擎。

## Exa 的工具职责

| Exa 工具 | 用途 | 关键条件 |
|---|---|---|
| `web_search_exa` | 普通网页、官方页面和候选来源发现 | 必填 `query` 与 `objective`；核对结果后读来源正文 |
| `web_fetch_exa` | 一条或多条已知网页 | 用 URL 数组；保存实际读到正文的来源 |
| `web_search_advanced_exa` | 域名、日期、类别、文本、时效、摘要、高亮、子页控制 | 先 `mcporter list exa --schema --all-parameters`；不把 REST 字段当成 MCP 参数 |
| `agent_run` | 多轮研究、候选逐项验证、结构化结果 | 普通任务 `low`；多标准交叉核验 `medium`；默认每任务一次，记录并续接同一 `runId` |

单个事实或已知页面优先 search/fetch。Agent 结果仍需开原始页面或原生平台核对；Exa 索引社交内容属于间接检索。维持 `exa-mcp.md` 的费用、运行记录、密钥和重试规则。

## 按渠道分工

| 渠道／领域 | 搜索与读取工具 | 调用要点、备用顺序 |
|---|---|---|
| 官方文档／标准 | 已知官方 URL 用 fetch；未知 URL 用网页搜索／Exa | 读原文、版本与日期；GitHub README/Release 可辅助，转载只作发现 |
| GitHub／代码 | GitHub MCP `search*`；本机 `gh search` | 仓库详情、文件、Release、Issue、PR 评论分别读取；不要用星数替代维护状态 |
| B站 | `bili search --page N -n 42 --page-info`；已验证的 OpenCLI `bilibili search` 浏览器备用 | yt-dlp `bilisearchN:` 仅条件备用；412 后转 OpenCLI，最后 Exa `site:bilibili.com/video` 间接检索；原始行、页元数据、无 BV 项和跨页 BV 去重分开记录 |
| YouTube | `yt-dlp ytsearchN`；OpenCLI `youtube/search` | `video` 元数据、`transcript`/字幕、`yt-comments` 评论分工；无字幕才按已有规则转录 |
| 小红书 | **固定 `xhs-cli + xhs-comments`**：`xhs --cookie-source chrome search "q" --json`；正文 `xhs --cookie-source chrome read "含 xsec_token 的笔记 URL" --json`；评论 `scripts/xhs-comments --url URL --max-pages N --json` | **禁止 OpenCLI 适配器、OpenCLI browser 及自动换用其他浏览器/MCP**；沙盒失败先在获准宿主重跑同一专用命令；仍失败报具体阻塞，允许的站外索引须标间接；评论 helper 内部浏览器签名不等于 OpenCLI |
| 知乎 | **关键词搜索固定 `zhihu-search` 官方 OpenAPI**，禁止 OpenCLI 搜索、browser 搜索及浏览器脚本替代 | API 失败先在获准宿主重跑同一 API 命令，仍失败报具体阻塞，不自动换路；凭证由 skill 私有 `.env` 读取；每查询最多 10 条且无已验证游标；正文与回答评论可分别用 `opencli zhihu answer-detail` / `answer-comments` 读取，不得用它们授权 OpenCLI 搜索 |
| 微博 | OpenCLI `weibo/search` | `post`、`comments`、`user-posts`；未登录不自动登录，间接网页结果独立标记 |
| X／Twitter | 可用时 `twitter search`；OpenCLI `twitter/search` | `thread`、`article`、`list-tweets`；`xurl` 仅作搜索/状态候选，当前机器未安装。直连失效后用 Exa `site:x.com OR site:twitter.com` 并标间接 |
| Reddit | `rdt --no-browser-cookies search`（只用保存凭据）或已有会话的 OpenCLI `reddit/search` | 保留 `after` 翻页、`read`、`comments`；403/无会话时转 Exa 站内搜索并标间接，不自动提取浏览器 Cookie |
| V2EX | OpenCLI `v2ex/node` 与公共 API 的节点列表 | `topic`、replies；无通用全文搜索时按相关节点查，再用站内网页发现并标间接 |
| 微信公众号 | `wechat-search`；Exa 限定 `mp.weixin.qq.com` | `wechat-article-for-ai` 读原文；本地 `wx` 只搜用户明确指定的本地缓存 |
| Facebook | OpenCLI `facebook/search` 与现有会话 | 读 profile/feed/帖子；群组限当前账号可见，登录墙登记阻塞 |
| Instagram | OpenCLI `instagram/search` 找账号 | 搜索对象为用户；再读 profile/user posts，不声称全站关键词帖子搜索 |
| LinkedIn | OpenCLI `linkedin/people-search`、`search` | 读职位/档案；`people-search` 会消耗平台月度额度，限任务相关调用。MCP 仅在已注册且实读后用 |
| 雪球／金融 | OpenCLI `xueqiu/search`，Ticker 行情用 `stock` | `comments`/`hot` 是讨论发现；行情与全文/社区搜索分开验证并读时间戳 |
| 抖音／TikTok | OpenCLI `douyin/search`、`tiktok/search` | 账号/视频/字幕/评论走各自 read 方法；登录要求逐项报告 |
| 小宇宙 | 先用网页/播客目录发现节目 | OpenCLI `xiaoyuzhou/episode`、`transcript`；缺转录可用已有转写通道 |
| RSS／博客 | 先发现相关作者/Feed；`feedparser` 读条目 | 追读原文；按发布日期和 feed 覆盖解释历史回溯，不把增量 Feed 当历史全集 |
| 社区／新闻搜索 | Hacker News、Linux.do、Stack Overflow 有 OpenCLI 搜索命令；Medium、Substack 也提供各自的搜索入口 | 按目录核对结果对象、登录策略与正文/评论命令；Linux.do 搜索需现有会话。命令发现不等于本次查询通过 |
| 社区／新闻发现 | Dev.to、Lobsters 以最新/热门/标签/域名列表与正文读取为主；Product Hunt 以浏览/热门/帖子列表为主 | 不称为通用关键词直搜；需要关键词时用 Exa 或宿主搜索的站点限定查询，并把结果标为间接 |
| 论坛／社区搜索与发现 | 泛指“搜论坛/搜社区”时使用持久 runner 的 `scope="forums"`，逐站覆盖 [12 个已登记社区](forums.md)；单站点名使用 focused scope | 论坛是待核验的目标站点，不是新的 Agent Reach 适配器。按下方论坛工作流记录直连/间接来源、活动证据和注册方式 |
| 学术 | `academic-literature-search` 规划来源；可用 OpenCLI arXiv、OpenAlex、PubMed、Crossref/知网/万方等直接端点 | 论文摘要/全文、DOI、引文是不同读取；Asta MCP 未在当前工具目录注册，先标未验证；缺失聚合器用直连源，不谎称覆盖 |
| 商品 | `buying-agent-cn` 负责选购研究；`cn-ecommerce-search-v2` 找链接；OpenCLI 淘宝/京东/亚马逊搜商品与 reviews | `maishou` 仅负责比价/优惠；标时间、SKU、平台。浏览器下单是独立用户任务 |
| 旅行／地点 | `tripai-skill` 查票/酒店；`maps` 查地理编码、POI 与路线 | 官方与实时结果核验；社区反馈仅用于体验，不替代票价/班次 |
| 软件／技能市场 | `unified-marketplace-search` 搜 LobeHub、SkillHub、skills.sh 和本地索引；点名 SkillDB 才用 `skilldb-search` | npm、NuGet、PyPI、Crates、DockerHub/HF 等原生 OpenCLI 搜包/模型；读仓库与发布状态 |
| AI 新闻／近期趋势 | `aihot` 查中文 AI 日报；RSS/官方公告查原始消息 | `last30days` 专做跨 Reddit/X/YouTube/TikTok/HN/Polymarket/GitHub 近 30 日讨论；遵守它自己的启动和输出合同 |
| 本地资料／旧会话 | 用户指定知识库走 `research-system` local library、Basic Memory、NotebookLM 或连接的 Docs 工具 | Planner/TickTick/B站目录仅在查这些任务/库存时调用；历史会话用 Conversation Archive；Deja 仅按其旧会话触发边界 |

当前 OpenCLI 可发现 179 个站点，其中 178 个提供只读命令，共 1,009 条（2026-10-15 快照，工具清单与实时 `opencli list` 逐条核对无差异；第 179 个站点 minimax 仅有 write 命令，不进路由）。注意两个口径：`opencli list` 的站点总数含 write-only 站点，快照的 `platforms_with_read_commands` 只数有只读命令的站点，比较时先对齐口径。每条命令的参数、分页字段、浏览器/登录策略、输出列、用途分类和未实测标记都在 JSON 清单；其中私有/工作区与账号状态命令不会自动进入公网搜索。357 个写命令未列入路由。

### 技术论坛与社区发现

用于发现与指定论坛相似的新社区，并核验其近期活动和公开注册路径。论坛站点是搜索结果，不代表存在对应的原生 Agent Reach 适配器。

1. **发现候选**：Exa `web_search_exa` 为主路由；准备两组互补的中英文查询，分别描述目标场景（如 Linux／AI 技术讨论、Linux.do 类中文社区）和候选／替代站点。用宿主 WebSearch 做独立交叉核对；扩展时加入新候选名称及“近期帖子、邀请码、开放注册、注册方式”等词。Exa 结果必须逐页筛查，不能把命令设置的结果数当作平台末页。
2. **识别站型并探测原生搜索**：确认站点是否公开全文查询，以及当前候选是否确实工作；不能因站点采用某论坛软件就默认每站端点可用。对公开 Discourse 站可实测 `/search.json?q=QUERY`，按 `more_full_page_results` 和 `page` 跟踪；`/latest.json`、RSS 仅是最新内容窗口，不等于全文搜索。Flarum 可检查 `/api/discussions?filter[q]=QUERY&page[limit]=N` 并沿响应 `links.next` 翻页。Discuz 从页面表单读取实际 `action`、GET/POST 与查询字段，再使用公开搜索结果的 `searchid` 和 `page` 跟踪分页；结果数量上限按页面实际提示记录。其他站点根据实际搜索表单/API核验。所有端点状态必须由真实查询结果确认，并记录域名、查询词、请求页、返回数、末页字段与错误；安装了 adapter、路径猜测、HTTP 200 空壳页都不算搜索通过。
3. **阅读原始内容**：对每个重点候选，打开原论坛帖或主题页；优先用 Jina Reader，Reader 不适用 JSON/API 时用公开原站主题端点读取正文。记录原始 URL、作者、发布日期、帖子/回复数及实际读到的内容。搜索摘要、JSON 命中 ID、HTTP 成功状态只算发现/可达证据，不算正文已读。
4. **核验活动与注册**：对公开首页、最新主题页和注册入口做只读 HTTP GET；记录状态码、页面可见的新帖时间和注册表单/SSO/邀请码说明。仅当注册页内容清楚显示可自行注册时标为“开放注册”；登录墙、反机器人、403、DNS 或空正文分别记录为访问限制，不从首页可达推断注册开放。不要提交注册、登录或发送注册/互动表单。
5. **补充原生讨论**：B站用 `bili search --page N -n 42 --page-info` 找社区测评/使用体验，并在相关时核对简介、字幕或实际内容；V2EX 用原生节点/主题路线找社区推荐和近期反馈。对无原生全文查询、需登录或被访问限制的论坛，继续用 Exa/WebSearch 站点限定发现并明确标为间接或受阻，不声称原生搜索。
6. **分页停止与限流**：仅当 API 明示无下一页/无更多结果或站点分页达到本次结果集末页，才称该条查询窗口翻完。遇到 400/429/403、登录墙或站点上限，保存响应状态并停止该条受限分页；可用不同同义词/场景查询补充召回，但不得重置 searchid、绕过访问控制或把截断结果称为完整。站外索引没有经验证游标时，记录工具实际返回数和未公开的总量/分页字段，不宣称全站搜全。
7. **形成推荐**：按论坛形态与目标相似度、近期活动、注册便利度、技术/AI 内容相关性整理候选；把官方站点说明、社区用户反馈和本机只读核验分开标证据。开放状态和活动度应带检索日期，遇到冲突保留不确定状态。

## 失败与备用

| 观察到的结果 | 下一步 |
|---|---|
| 配置未发现／可执行文件缺失 | 标 `unavailable`；用已安装的下一条路线；不安装、不登录 |
| 登录墙、验证码、反机器人 | 标 `access_blocked`；改走公开索引并标 `indirect`，继续独立渠道 |
| DNS、代理、TLS、超时 | 保存错误类型；检查代理环境/目标端点；用另一个已配置通道；不要把传输失败报成平台无结果 |
| 429、403、412、特定 endpoint 错误 | 遵循平台文档的有界重试；限制可能影响单 endpoint，不外推整个平台 |
| 空结果或只有标题/snippet | 核实 query、页码、内容读取状态；必要时扩词/换排序；保持 discovered-only 或真实 no-result |
| 页面已发现、正文/评论/字幕失败 | 对应内容读取器走备用；证据账本保留发现与读取两种结果 |

同一工具状态按 `configured → tool discovered → query returned items → relevant content read` 逐级记录。直接适配器和间接搜索分开留痕；兼容的评论工具不能代替分页证明。
