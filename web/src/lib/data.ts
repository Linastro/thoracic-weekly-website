/** 构建期加载 snapshot JSON。容器路径 + 本地 fallback。 */

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import type { Article, DailySnapshot } from './types';

/** 优先从容器路径 /data/snapshots 读,fallback 到 mock 数据。 */
const SNAPSHOT_PATHS = [
  '/data/snapshots',
  join(process.cwd(), 'data', 'snapshots'),
  join(process.cwd(), '..', 'data', 'snapshots'),
];

function findSnapshotDir(): string | null {
  for (const p of SNAPSHOT_PATHS) {
    if (existsSync(p)) return p;
  }
  return null;
}

/** mock 数据 — 本地无 snapshot 时使用。 */
function mockSnapshots(): DailySnapshot[] {
  return [
    {
      date: '2026-07-30',
      generated_at: '2026-08-01T00:00:00+00:00',
      article_count: 2,
      articles: [
        {
          pmid: 'mock-1',
          title: 'Mock Article 1: Lung Cancer Trial',
          title_zh: '示例文章 1:肺癌临床试验',
          abstract: 'Sample abstract...',
          abstract_zh: '示例摘要...',
          authors: ['Author A', 'Author B'],
          affiliations: ['Hospital X', 'University Y'],
          journal: 'Lancet',
          journal_full: 'The Lancet',
          journal_abbr: 'Lancet',
          doi: null,
          publication_types: ['Journal Article', 'Multicenter Study'],
          pubdate: '2026 Jul 30',
          epdat: '2026-07-30',
          fetched_at: '2026-08-01T00:00:00+00:00',
          disease: 'lung_cancer',
          type: 'clinical',
          impact_factor: 109.0,
          jcr_quartile: 'Q1',
          new_talent_quartile: '1区',
          matched_jcr: 'The Lancet',
          llm_model: '',
          llm_excluded: 0,
          llm_needs_review: 0,
        },
      ],
    },
  ];
}

/** 加载所有 snapshot,按日期倒序。 */
export function loadAllSnapshots(): DailySnapshot[] {
  const dir = findSnapshotDir();
  if (!dir) {
    console.warn('[data] no snapshot dir found, using mock data');
    return mockSnapshots();
  }
  const files = readdirSync(dir)
    .filter((f) => f.endsWith('.json'))
    .sort()
    .reverse();
  return files.map((f) => {
    const content = readFileSync(join(dir, f), 'utf-8');
    return JSON.parse(content) as DailySnapshot;
  });
}

/** 扁平所有 articles(跨日期),按 epdat 倒序。
 *
 * 防御性过滤 `llm_excluded === 0`:即便 snapshot 文件脏(含陈旧 exclude 或跨日重复),
 * 也不让被 LLM 排除的文章漏到前端。第 13 步 snapshot 重建后此过滤为空集,但保留作为
 * 防御层。
 */
export function loadAllArticles(): Article[] {
  const snaps = loadAllSnapshots();
  const seen = new Set<string>();
  const out: Article[] = [];
  for (const a of snaps.flatMap((s) => s.articles)) {
    if (a.llm_excluded !== 0) continue;
    if (seen.has(a.pmid)) continue;
    seen.add(a.pmid);
    out.push(a);
  }
  return out;
}

/** 加载单个 PMID 的 article(从 snapshot 找)。 */
export function loadArticleByPmid(pmid: string): Article | null {
  for (const a of loadAllArticles()) {
    if ( a.pmid === pmid) return a;
  }
  return null;
}

/** 加载指定日期的 snapshot。 */
export function loadSnapshotByDate(date: string): DailySnapshot | null {
  for (const s of loadAllSnapshots()) {
    if (s.date === date) return s;
  }
  return null;
}