/**
 * 构建期加载 weekly 周报 JSON。
 * 后端每周产出 {snapshotDir}/weekly/{week_start}-{week_end}.json。
 * 路径解析参考 data.ts(SNAPSHOT_PATHS + findSnapshotDir)。
 */

import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

/** 优先从容器路径 /data/snapshots 读,fallback 到本地 data/snapshots。 */
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

/** 周报单篇参考文献。 */
export interface WeeklyReference {
  ref_no: number;
  pmid: string;
  authors: string[];
  title: string;
  journal_full: string;
  pubdate: string;
  doi: string | null;
  impact_factor: number | null;
  jcr_quartile: string | null;
  new_talent_quartile: string | null;
}

/** 周报研究类型小节(综述正文 + 引用标记)。 */
export interface WeeklySubsection {
  type: string;
  type_zh: string;
  summary: string;
}

/** 周报病种节。 */
export interface WeeklySection {
  disease: string;
  disease_zh: string;
  article_count: number;
  subsections: WeeklySubsection[];
}

/** 单期周报(对应 weekly/{week_start}-{week_end}.json)。 */
export interface WeeklyReport {
  week_start: string;
  week_end: string;
  generated_at: string;
  total_articles: number;
  sections: WeeklySection[];
  references: WeeklyReference[];
}

/** 加载所有周报,按 week_start 倒序(最新在上)。 */
export function loadWeeklyReports(): WeeklyReport[] {
  const dir = findSnapshotDir();
  if (!dir) return [];
  const weeklyDir = join(dir, 'weekly');
  if (!existsSync(weeklyDir)) return [];
  const reports = readdirSync(weeklyDir)
    .filter((f) => f.endsWith('.json'))
    .map((f) => {
      const content = readFileSync(join(weeklyDir, f), 'utf-8');
      return JSON.parse(content) as WeeklyReport;
    });
  // 按 week_start 字段排序,与文件名无关
  reports.sort((a, b) =>
    a.week_start < b.week_start ? 1 : a.week_start > b.week_start ? -1 : 0,
  );
  return reports;
}

/** 按 week_start 匹配单期周报;找不到返回 null。 */
export function loadWeeklyReport(weekStart: string): WeeklyReport | null {
  return loadWeeklyReports().find((r) => r.week_start === weekStart) ?? null;
}

/** 格式化周区间显示:2026-07-20 / 2026-07-26 → 「2026.07.20 – 07.26」。 */
export function formatWeekRange(weekStart: string, weekEnd: string): string {
  const s = weekStart.replace(/-/g, '.');
  const e = weekEnd.slice(5).replace(/-/g, '.');
  return `${s} – ${e}`;
}

/** 展开引用内部字符串([n]/[n-m]/[n,m] 的内容部分)为数字数组。 */
function expandRefs(inner: string): number[] {
  const out: number[] = [];
  for (const part of inner.split(',')) {
    const t = part.trim();
    const m = /^(\d+)\s*-\s*(\d+)$/.exec(t);
    if (m) {
      const lo = Math.min(parseInt(m[1], 10), parseInt(m[2], 10));
      const hi = Math.max(parseInt(m[1], 10), parseInt(m[2], 10));
      for (let i = lo; i <= hi; i++) out.push(i);
    } else if (/^\d+$/.test(t)) {
      out.push(parseInt(t, 10));
    }
  }
  return out;
}

/**
 * 把综述正文里的 [n]/[n-m]/[n,m] 引用渲染成彩色上标锚点链接(返回 HTML 字符串)。
 * [1-3] 这类范围会拆成 1、2、3 各自锚点;正文先做 HTML 转义再替换,避免破坏结构。
 */
export function renderSummaryHtml(summary: string): string {
  const escaped = summary
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  return escaped.replace(/\[(\d+(?:[,\-]\d+)*)\]/g, (_m, inner: string) =>
    expandRefs(inner)
      .map((n) => `<sup class="cite"><a href="#ref-${n}">[${n}]</a></sup>`)
      .join(''),
  );
}
