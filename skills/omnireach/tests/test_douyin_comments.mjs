import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const source = await readFile(new URL('../scripts/douyin-comments/_shared-public-api.js', import.meta.url), 'utf8');
const executable = source
    .replace(/^import .*;\s*/m, '')
    .replaceAll('export async function', 'async function') + '\nreturn fetchDouyinCommentsPage;';
class Params {
    constructor(values) { this.values = values; }
    toString() { return new URLSearchParams(this.values).toString(); }
}
class CommandExecutionError extends Error {}
const makeFetchPage = browserFetch => new Function('browserFetch', 'URLSearchParams', 'CommandExecutionError', executable)(
    browserFetch, Params, CommandExecutionError,
);

test('valid terminal empty response is a real empty page', async () => {
    const fetchPage = makeFetchPage(async () => ({ comments: [], has_more: false, cursor: 0 }));
    assert.deepEqual(await fetchPage({}, '12345', 50, 0), { comments: [], cursor: 0, has_more: false });
});

test('missing comments array is rejected', async () => {
    const fetchPage = makeFetchPage(async () => ({ code: -100, message: 'not authenticated' }));
    await assert.rejects(fetchPage({}, '12345', 50, 0), /comments must be an array/);
});

test('missing pagination status is rejected', async () => {
    const fetchPage = makeFetchPage(async () => ({ comments: [] }));
    await assert.rejects(fetchPage({}, '12345', 50, 0), /has_more is missing/);
});

test('non-advancing cursor is rejected', async () => {
    const fetchPage = makeFetchPage(async () => ({ comments: [], has_more: 1, cursor: 0 }));
    await assert.rejects(fetchPage({}, '12345', 50, 0), /cursor is missing or unchanged/);
});

test('valid next page carries cursor and comments', async () => {
    const fetchPage = makeFetchPage(async () => ({ comments: [{ cid: 'c1' }], has_more: 1, cursor: 25 }));
    assert.deepEqual(await fetchPage({}, '12345', 50, 0), {
        comments: [{ cid: 'c1', text: '', digg_count: 0, nickname: '', reply_comment_total: 0 }],
        cursor: 25,
        has_more: true,
    });
});
