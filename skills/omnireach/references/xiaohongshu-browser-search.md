# 小红书：已退役的首页搜索记录（禁止作为路由）

2026-10-05 首测，2026-10-06 复测：Chrome 154.0.8037.98、OpenCLI 1.8.8、扩展 1.0.24。
用户已登录并手动完成验证后，从首页搜索框搜索“咖啡”成功，进入
`/search_result_ai`，读到真实笔记标题、作者和链接，页面没有验证码。
普通 `opencli xiaohongshu search` 在同次排查中仍报 5 秒内容超时。

## 2026-10-21 起的固定规则

本页仅保留旧浏览器流程的历史观察，不再提供可执行的 OpenCLI 操作配方。
**搜索、正文和顶层评论固定走 browser-native 的 `xiaohongshu-mcp`（`scripts/xhs-mcp`），`xhs` CLI 为搜索正文备选，TikHub App V2 仅在需要二级回复或更多页时启用；禁止小红书的 OpenCLI 适配器与通用 browser，失败也不得回退。** 下面的本机评论命令只作为明确选择的顶层评论备用。当前规则见 [social.md](social.md)、[xiaohongshu-mcp.md](xiaohongshu-mcp.md)、[渠道速查表](channel-routing-cheatsheet.md) 和 [路由清单](route-manifest.json)。
当前规则见 [social.md](social.md)、[渠道速查表](channel-routing-cheatsheet.md) 和 [路由清单](route-manifest.json)。

## 当前命令

```bash
<skill-root>/scripts/xhs-mcp search "关键词"                                    # 主路由
<skill-root>/scripts/xhs-mcp detail --feed-id FEED_ID --xsec-token TOKEN [--load-all-comments]
<skill-root>/scripts/xhs-mcp status                                              # 读当前登录用户
<skill-root>/scripts/xhs-mcp unread-count                                        # 只读通知计数
xhs --cookie-source chrome search "关键词" --json                                 # 备选：搜索
xhs --cookie-source chrome read "NOTE_ID" --json                                  # 备选：正文
<skill-root>/scripts/xhs-comments --url "NOTE_URL_WITH_XSEC_TOKEN" --max-pages 3 --json  # 明确选择时的顶层评论备用
```

正文与顶层评论优先用搜索结果里的**笔记级** `xsec_token`（feed item 顶层的 `xsecToken`），不要用作者令牌 `note_card.user.xsec_token`；`scripts/xhs-mcp search` 会同时打印 `id` 和 `xsec_token`。走 `xhs` CLI 备选时仍优先用**裸笔记 ID**（CLI 用自己的令牌缓存）；Cookie 缓存在超过 7 天或会话失效时才从浏览器重读，浏览器验证后请显式执行 `xhs login --cookie-source chrome` 刷新缓存。

`scripts/xhs-comments` 内部调用浏览器原生签名，不依赖 OpenCLI；这不构成恢复旧浏览器搜索的例外。

## 历史观察（不作为当前指令）

- 旧流程曾从首页可见搜索框进入 `/search_result_ai` 并读到真实笔记；默认适配器在同次排查中仍超时。
- 当时可见输入框为 `#search-input-in-feeds`，另两个输入框隐藏；提交图标也存在隐藏与可见两份，固定序号不可靠。
- `Navigation rejected` 曾涉及 OpenCLI / Chromium 跳转兼容性，不能证明用户登录失效。
- 旧记录只验证了首页搜索，没有验证详情、评论、筛选和深翻页；不得据此升级当前能力状态。
- 当前 CLI 遇到沙盒/缓存权限问题时，在获准宿主重跑同一条命令；会话过期、验证码或限流则报告准确阻塞，不重启这条退役路线。
