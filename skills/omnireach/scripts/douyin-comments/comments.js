// omnireach douyin comments — 薄包装：读取任意抖音视频的评论列表（支持 cursor 翻页）
// 权威源: /Users/mac/LocalSkills/统一技能库/sources/desktop-local/common/omnireach/scripts/douyin-comments/comments.js
// 安装: 本文件 + _shared-{public-api,browser-fetch,evaluate-result}.js（去掉 _shared- 前缀，public-api 用本目录扩展版）
//       拷入 ~/.opencli/clis/douyin/（_shared 三件进 _shared/ 子目录）；卸载: 删除 ~/.opencli/clis/douyin/
// 数据面: aweme/v1/web/comment/list；--pages N|all 翻页（每页 50，按 cid 去重）；仅一级评论，二级回复正文不在此端点
import { cli, Strategy } from '@jackwener/opencli/registry';
import { ArgumentError } from '@jackwener/opencli/errors';
import { fetchDouyinCommentsPage } from './_shared/public-api.js';

const PER_PAGE = 50;
const MAX_PAGES = 100;

cli({
    site: 'douyin',
    name: 'comments',
    access: 'read',
    description: '读取任意抖音视频的评论列表（aweme_id 或视频 URL；--pages N/all 翻页）',
    domain: 'www.douyin.com',
    strategy: Strategy.COOKIE,
    args: [
        { name: 'ref', type: 'string', required: true, positional: true, help: 'aweme_id 或 https://www.douyin.com/video/<id>' },
        { name: 'count', type: 'int', default: 20, help: '条数上限（≤50；仅在 --pages 1 时生效，多页模式每页固定 50）' },
        { name: 'pages', type: 'string', default: '1', help: "页数：1=仅首页（默认，≠完整列表）；N=N 页；all=翻到没有更多（安全上限 100 页）" },
        { name: 'meta', type: 'bool', default: false, help: '返回分页完整性元数据；Omnireach 取证流程应启用（--meta）' },
    ],
    columns: ['index', 'nickname', 'text', 'digg_count', 'reply_comment_total'],
    func: async (page, kwargs) => {
        const fromUrl = String(kwargs.ref ?? '').match(/video\/(\d+)/);
        const awemeId = fromUrl ? fromUrl[1] : String(kwargs.ref ?? '').trim();
        if (!/^\d{5,}$/.test(awemeId)) {
            throw new ArgumentError('ref 必须是 aweme_id 或抖音视频 URL', 'aweme_id 可从 opencli douyin search 输出的 url 字段取得');
        }
        const pagesArg = String(kwargs.pages ?? '1').trim().toLowerCase();
        const wantAll = pagesArg === 'all';
        const pages = wantAll
            ? MAX_PAGES
            : Math.min(MAX_PAGES, Math.max(1, Math.round(Number(pagesArg) || 1)));
        const firstOnly = !wantAll && pages === 1;
        const seen = new Set();
        const out = [];
        const seenCursors = new Set([String(0)]);
        let cursor = 0;
        let complete = false;
        let stopReason = 'page_limit';
        let hasMore = null;
        let pagesFetched = 0;
        for (let p = 1; p <= pages; p++) {
            const per = firstOnly
                ? Math.min(PER_PAGE, Math.max(1, Math.round(Number(kwargs.count) || 20)))
                : PER_PAGE;
            const res = await fetchDouyinCommentsPage(page, awemeId, per, cursor);
            pagesFetched++;
            for (const c of res.comments) {
                if (c.cid && seen.has(c.cid)) continue;
                if (c.cid) seen.add(c.cid);
                out.push(c);
            }
            hasMore = res.has_more;
            if (!res.has_more) {
                complete = true;
                stopReason = 'platform_exhausted';
                break;
            }
            if (seenCursors.has(String(res.cursor))) {
                stopReason = 'repeated_cursor';
                break;
            }
            cursor = res.cursor;
            seenCursors.add(String(cursor));
        }
        const comments = out.map((c, i) => ({ index: i + 1, ...c }));
        if (!kwargs.meta) return comments;
        return {
            comments,
            status: complete ? 'success' : 'partial',
            complete,
            pages_fetched: pagesFetched,
            stop_reason: stopReason,
            has_more: hasMore,
            cursor,
        };
    },
});
