/** 期刊目录(从仓库根的 journal_metrics.json 加载,按字母排序)。
 *
 * 路径:web/src/lib/journals.ts → ../../journal_metrics.json
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export interface Journal {
  journal: string;
  impact_factor: number | null;
  jcr_quartile: string | null;
  new_talent_quartile: string | null;
}

const resolveMetricsPath = (): string => {
  const here = path.dirname(fileURLToPath(import.meta.url));
  return path.resolve(here, '..', '..', '..', 'journal_metrics.json');
};

export const loadJournals = (): Journal[] => {
  const p = resolveMetricsPath();
  if (!fs.existsSync(p)) {
    console.warn(`[journals] journal_metrics.json not found at ${p}, returning empty list.`);
    return [];
  }
  try {
    const raw = fs.readFileSync(p, 'utf-8');
    const data = JSON.parse(raw) as { journals?: Journal[] };
    const list = Array.isArray(data.journals) ? data.journals : [];
    return [...list].sort((a, b) => a.journal.localeCompare(b.journal));
  } catch (err) {
    console.warn(`[journals] failed to parse ${p}:`, err);
    return [];
  }
};
