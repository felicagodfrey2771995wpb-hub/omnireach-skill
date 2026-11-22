# 小红书 browser-native 路由（xiaohongshu-mcp）与验收

## 为什么需要这条路线

`xhs` CLI 走的是签名 API。这条路**在上游已经被封死**，本机文档里早有记录：

- `api/v4/search_v3` 与 `api/v4/members/{token}/answers` 在**国内和国外出口都返回 HTTP 403 空 body**，
  而 `api/v4/me` 成功 —— 也就是说 cookie 链是健康的，被 WAF 拒的是 `x-zse-96` 签名
  （见 [social.md](social.md) 的 "Session import and the signature ceiling"）。
- `api/sns/web/v2/comment/page` 同样在国内外出口返回 **HTTP 406 空 body**，
  响应头带 `Access-Control-Allow-Headers: f,x-s,x-sign,x-t` 与 `X-Kong-Sign: 1`，
  说明是网关在校验签名，且这个签名**无法调通**。

`scripts/xhs-comments` 当初正是为此才改成浏览器原生签名。`xiaohongshu-mcp` 把同一思路
推广到了**搜索 + 正文 + 评论**：它驱动真实浏览器，**由页面自己签名**，完全不碰签名墙。

2026-11-22 本机实测 `xhs search` 返回 `verification_required`，而 `xiaohongshu-mcp`
同日搜索返回 20 条真实笔记。这就是两条路线的实际差距。

## 两条接入路径

| 路径 | 入口 | 适合 |
|---|---|---|
| **skill 脚本** | `<skill-root>/scripts/xhs-mcp` | omnireach 的渠道路由走这条；任何宿主都能用；不需要注册 MCP server |
| **原生 MCP server** | 工具 `search_feeds` / `get_feed_detail` / `user_profile` / `get_my_profile` / `list_feeds` / `check_login_status` / `get_unread_count` | 宿主已注册该 MCP server 时直接调工具 |

两条路径打的是同一个上游（`xiaohongshu-mcp` v2.7.4），**结果一致**。

原生 MCP server 由部署目录里的 `mcp-stdio.py` 提供：上游只支持 HTTP（Streamable HTTP，
跑在 `/mcp`），而宿主按 stdio 注册 MCP server，这个脚本负责桥接。它**只暴露 7 个只读工具**，
写工具在 `tools/call` 层就被拒绝（不是只在 `tools/list` 里藏起来——上游的 `delete_cookies`
真的会删掉会话文件，`publish_content` 真的会发出去）。

各端注册位置：

| 端 | 配置 |
|---|---|
| opencode | `~/.config/opencode/opencode.json` → `mcp.xiaohongshu` |
| codex | `~/.codex/config.toml` → `[mcp_servers.xiaohongshu]` |
| hermes | `~/.hermes/config.yaml` → `mcp_servers.xiaohongshu` |
| workbuddy | `~/.workbuddy/.mcp.json` → `mcpServers.xiaohongshu` |
| zcode | `~/.zcode/cli/config.json` → `mcp.servers.xiaohongshu`，`~/.agents/mcp.json` 同源 |

命令都是 `/opt/homebrew/bin/python3 <部署根>/mcp-stdio.py`，环境变量 `XHS_MCP_HOME` 指向部署根。

## 部署

| 项 | 值 |
| --- | --- |
| 代码 | https://github.com/xpzouying/xiaohongshu-mcp （Apache-2.0，v2.7.4） |
| 部署根 | `~/Work/projects/codex/app-data/xiaohongshu-mcp` （可用 `XHS_MCP_HOME` 覆盖） |
| 二进制 | `bin/xiaohongshu-mcp`（Go，arm64）；只提供 HTTP，MCP 跑在 `:18060/mcp` |
| 内置浏览器 | `148.0.7778.215`，缓存在 `~/Library/Caches/xiaohongshu-mcp/browser/<version>/` |
| 会话文件 | `data/cookies.json`（`version` / `seed` / `saved_at` / `cookies`） |
| 指纹 | `seed` 固定在会话文件里；`XHS_FP_SEED` **刻意不设** |

上游只认内置浏览器：`browser.NewBrowser` 走 `EnsureBrowser()`，取不到就 `panic`，
代码注释写明"宁可不启动，也不启动一个不对的浏览器"。**不要改成真实 Chrome**：
真 Chrome 不认识 `--fingerprint*` flag（会静默忽略），且版本漂移会改掉 TLS/JA4 指纹。

会话文件路径由部署的 `env.sh` 钉成绝对路径。上游默认会退回相对 `./cookies.json`，
换个工作目录启动就会**静默生成新 seed（新指纹）**并只打一行 warn。

## 执行入口

统一入口是本 skill 的只读客户端 `scripts/xhs-mcp`。它**每次调用拉起一个独立服务实例**
（随机空闲端口，退出时回收），因此会话完全确定：永远读同一个 `cookies.json`、同一个 seed。

```bash
<skill-root>/scripts/xhs-mcp status                 # 读当前登录用户（用 /api/v1/user/me）
<skill-root>/scripts/xhs-mcp search "关键词"          # 搜索
<skill-root>/scripts/xhs-mcp detail --feed-id ID --xsec-token TOKEN --load-all-comments
<skill-root>/scripts/xhs-mcp user-profile USER_ID --xsec-token TOKEN [--tab note|fav|liked]
<skill-root>/scripts/xhs-mcp my-profile
<skill-root>/scripts/xhs-mcp unread-count           # 只读，不清未读标记
<skill-root>/scripts/xhs-mcp list-feeds             # 首页 feeds
<skill-root>/scripts/xhs-mcp login-status           # 原始 /login/status，跨洋出口下可能超时
```

加 `--json` 输出原始 payload。每条命令都在 stderr 打印 `[backend] xiaohongshu-mcp (browser-native)`，
**报告里必须带上这个后端标注**。

客户端只暴露读命令。发布、评论、点赞、收藏、删 cookie 这些写路由**一律不暴露**。

### 取 note 级 token 的规则不变

`detail` 和 `user-profile` 都**必须**带 `xsec_token`：

- 用搜索结果里的**笔记级** token，即 feed item 顶层的 `xsecToken`
- **绝不能**用作者 token `noteCard.user.xsec_token`（那是另一个 token，会失败）
- `scripts/xhs-mcp search` 的输出已经同时打印 `id` 和 `xsec_token`，直接复制

### 搜索没有分页

上游 `feeds/search` 只有 `keyword` 和 `filters`（`sort_by` / `note_type` /
`publish_time` / `search_scope` / `location`），**没有 page 参数**。一次返回 20 条。
需要更多内容时换关键词，或走 `user-profile --tab note` 拉某个作者的作品列表。

## 路由决策

| 需求 | 主路由 | 备选 |
| --- | --- | --- |
| 搜索 | `scripts/xhs-mcp search` | `xhs --cookie-source chrome search "q" --json`（签名墙风险高） |
| 笔记正文 | `scripts/xhs-mcp detail`（正文 + 评论 + 字幕一次拿全） | `xhs --cookie-source chrome read "NOTE_ID" --json` |
| 顶层评论 | `scripts/xhs-mcp detail`（免费、浏览器原生、含 `hasMore`/`cursor`） | `scripts/xhs-tikhub-comments`（付费额度，用于二级回复或更多页） |
| 字幕 | `scripts/xhs-mcp detail` 返回的 `video.subtitles` 签名直链 | 之前是 `not_verified` |
| 用户主页 | `scripts/xhs-mcp user-profile` / `my-profile` | — |
| 通知 | `scripts/xhs-mcp unread-count`（只读） | — |

**降级链是单向的**：`xiaohongshu-mcp` 失败 → `xhs` CLI → 报告精确阻塞。
**任何一步失败都不解锁 OpenCLI 或通用浏览器/MCP 路线。** 这条底线不变。

### 什么情况下启用 TikHub

`detail` 返回的是**第一页**评论（实测 14 条 / 一条 23 评的笔记拿到 14 条）。
需要**二级回复**、**跨页续读**或**折叠评论覆盖**时，才启用
`scripts/xhs-tikhub-comments`。普通"看看评论"不必消耗付费额度。

## 失败分类

| 现象 | 分类 | 处理 |
| --- | --- | --- |
| `timeout`（`context deadline exceeded`） | 出口延迟 | 换关键词重试；见下面「出口」一节 |
| `no_feeds_data`（"没有捕获到 feeds 数据"） | 8 秒注水窗口不够 | 同上；或改用 `search` / `detail` |
| `not_authenticated`（"login status element not found"） | 会话失效 | 用户在浏览器重新登录后刷新会话文件 |
| `invalid_request` | 参数缺（多为缺 `xsec_token`） | 补参数重试 |
| `service_unavailable` | 服务没起来 | 看 `~/Work/projects/codex/app-data/xiaohongshu-mcp/logs/xhs-mcp-client.log` |
| `http_500` + `context deadline exceeded` | `/explore` 类接口超时 | 用 `status`（走 `/user/me`）代替 `login-status` 判断会话 |

**`verification_required` 的处理链不变**：用户在浏览器完成验证 → 刷新 cookie 缓存 →
重试。不要用重复请求去冲。

## 出口（重要）

本机 Shadowrocket 跑 **TUN 全局模式**，出口是 **US Los Angeles** 的公网地址（此处不记录具体 IP）。
2026-11-22 实测：

| 请求 | 结果 |
| --- | --- |
| 无 cookie → `xiaohongshu.com/explore` | **302** → `https://www.rednote.com/explore` |
| 带 cookie → 同一 URL | **200**，不跳转，约 3.4s |

无 cookie 时小红书按 GeoIP 把匿名访客丢到国际版 rednote.com，**那个页面不弹二维码**，
所以上游的扫码登录流程在本机会一直挂着等 `.qrcode-img`。这是**出口问题，不是浏览器问题**。

跨洋出口还会顶爆上游按国内网络调的内部超时：

- `xiaohongshu/feeds.go:48` —— `__INITIAL_STATE__.feed` 注水窗口只有 **8 秒**
- `xiaohongshu/login.go` —— `CheckLoginStatus` 导航超时 **30 秒**

实测 `/api/v1/login/status` **两次里失败一次**（31.9s 成功 / 32.1s 超时 / 25.5s 成功），
`/api/v1/feeds/list` **两次全败**。`/api/v1/user/me` 与 `/api/v1/feeds/search` 稳定。

**建议**：在 Shadowrocket 加一条 `DOMAIN-SUFFIX,xiaohongshu.com,DIRECT`（或切中国出口）。
这同时解决延迟、扫码无二维码和风控风险三件事。**不要单方面改用户的代理配置**——
提出建议，让用户自己应用，然后验证出口 IP 并重跑路线。

上游的内部超时也可以自己改后重编译（`feeds.go` 8 秒、`login.go` 30 秒）。
浏览器版本仍从 `browser/browser_version.txt` 读取，不重新下载，指纹和登录态不受影响；
但从此要自己维护 fork。

## 已知限制

- **跨洋出口下读取会间歇失败**：实测 `/api/v1/user/me` 4 次里 1 次上游返回 HTTP 500，
  另有若干次返回 `success: true` 但 `userBasicInfo` 为空（页面没完全注水）。
  `scripts/xhs-mcp` 因此带一层**内容校验**：空 payload 被判为 `empty_payload` 失败，
  而不是当成成功返回——否则会把「没读到」误报成「读到了空账号」。
  `health.sh` 用同样的判据。
- **发布当前不可用**：上游 issue #919 / #921（2026-11-20 / 21，均 OPEN）。
  创作者中心已不再下发 `galaxy_creator_session_id`，而 `xiaohongshu/creator_session.go`
  靠检查这个 cookie 判断会话，所以 `publish_content` 必然报"创作者中心登录失效"。
  读操作不受影响。本 skill 只读，也不暴露发布。
- **评论只有第一页**：`detail` 返回首屏评论 + `hasMore` + `cursor`，不含二级回复正文。
- **会话是快照不是滚动会话**：上游只在登录那一刻写一次 cookies，每次工具调用都新建
  浏览器、用完销毁，请求中服务端下发的 `Set-Cookie` 会被丢弃。过期后重新导入即可
  （`import-from-chrome.sh`，不需要扫码）。
- **跨洋出口慢**：见上面「出口」。这是当前本机最主要的稳定性风险。

## 本机实测（2026-11-22）

| 项目 | 结果 |
| --- | --- |
| `status`（`/api/v1/user/me`） | HTTP 200 · 返回已登录用户（昵称与小红书号已脱敏）· 关注 3 · 粉丝 0 |
| `search "露营装备"` | 20 条真实笔记，每条带 `id` 与 `xsecToken` |
| `search "咖啡探店"` | 20 条真实笔记 |
| `detail`（`6a8763010000000008009c00`） | 标题 + 作者 + 互动（赞 554 / 藏 630 / 评 23）+ **14 条真实评论**，`hasMore=false` |
| `detail`（视频笔记 `6a37af98000000001c024ecb`） | 正文 + 2 条评论 + `video.subtitles` 的 zh-CN / en-US 签名直链 |
| 字幕直链 | HTTP 200，1391 B，有效 SRT，中文内容 |
| `unread-count` | `mentions/likes/connections/unread` = 0/0/0/0 |
| `login-status` | 25–32s，**约 50% 超时**（跨洋出口，见上） |
| `list-feeds` | 2/2 失败，"没有捕获到 feeds 数据"（8 秒注水窗口） |

## 边界

- 客户端**只读**：不登录、不扫码、不写 cookie、不发任何写请求。
- `list_notifications` 会清除未读标记，因此**不暴露**；只保留 `get_unread_count`。
- 上游 `publish_content` / `post_comment_to_feed` / `like_feed` / `favorite_feed` /
  `delete_cookies` 一律不暴露。
- 同一账号不要在别的网页端登录（上游 README 明确写了小红书不允许多网页端，会互踢）。
