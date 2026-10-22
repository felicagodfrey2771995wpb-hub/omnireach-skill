import { browserFetch } from './browser-fetch.js';
export async function fetchDouyinUserVideos(page, secUid, count) {
    const params = new URLSearchParams({
        sec_user_id: secUid,
        max_cursor: '0',
        count: String(count),
        aid: '6383',
    });
    const data = await browserFetch(page, 'GET', `https://www.douyin.com/aweme/v1/web/aweme/post/?${params.toString()}`, {
        headers: { referer: 'https://www.douyin.com/' },
    });
    return data.aweme_list || [];
}
export async function fetchDouyinComments(page, awemeId, count) {
    const params = new URLSearchParams({
        aweme_id: awemeId,
        count: String(count),
        cursor: '0',
        aid: '6383',
    });
    const data = await browserFetch(page, 'GET', `https://www.douyin.com/aweme/v1/web/comment/list/?${params.toString()}`, {
        headers: { referer: 'https://www.douyin.com/' },
    });
    return (data.comments || []).slice(0, count).map((comment) => ({
        text: comment.text || '',
        digg_count: comment.digg_count ?? 0,
        nickname: comment.user?.nickname || '',
    }));
}
// omnireach 扩展：页级读取（返回 cursor/has_more，供 comments.js 翻页）；上游 fetchDouyinComments 保持原样不动
export async function fetchDouyinCommentsPage(page, awemeId, count, cursor) {
    const params = new URLSearchParams({
        aweme_id: awemeId,
        count: String(count),
        cursor: String(cursor ?? 0),
        aid: '6383',
    });
    const data = await browserFetch(page, 'GET', `https://www.douyin.com/aweme/v1/web/comment/list/?${params.toString()}`, {
        headers: { referer: 'https://www.douyin.com/' },
    });
    return {
        comments: (data.comments || []).map((comment) => ({
            cid: String(comment.cid || ''),
            text: comment.text || '',
            digg_count: comment.digg_count ?? 0,
            nickname: comment.user?.nickname || '',
            reply_comment_total: comment.reply_comment_total ?? 0,
        })),
        cursor: data.cursor ?? 0,
        has_more: !!data.has_more,
    };
}
