import { useMemo, useState } from 'react';
import type { Article } from '../lib/types';
import { DISEASES, TYPES } from '../lib/types';
import './SearchIsland.css';

interface Props {
  /** 初始文章列表(由 .astro frontmatter 注入,客户端再过滤) */
  articles: Article[];
  /** 当前 filter chip 状态(由 URL 解析得到) */
  disease?: string;
  type?: string;
}

/**
 * 把搜索框 + 结果列表合并到单个 React island,共用 React state。
 * - SearchBox 输入 → setQuery → 派生 results
 * - 直接渲染卡片(原本由 .astro DateGroup + ArticleCard 渲染)
 * - 不再使用自定义事件总线(React state 已是最简方案)
 */

function formatDate(date: string): string {
  const d = new Date(date + 'T00:00:00');
  const weekday = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()];
  return `${d.getMonth() + 1}月${d.getDate()}日 星期${weekday}`;
}

function score(article: Article, lower: string): number {
  let s = 0;
  if ((article.title ?? '').toLowerCase().includes(lower)) s += 10;
  if ((article.title_zh ?? '').toLowerCase().includes(lower)) s += 10;
  if ((article.abstract ?? '').toLowerCase().includes(lower)) s += 3;
  if ((article.abstract_zh ?? '').toLowerCase().includes(lower)) s += 3;
  if ((article.journal_full ?? '').toLowerCase().includes(lower)) s += 2;
  if ((article.journal ?? '').toLowerCase().includes(lower)) s += 2;
  if (article.authors.some((a) => a.toLowerCase().includes(lower))) s += 1;
  return s;
}

export default function SearchIsland({ articles, disease, type }: Props) {
  const [q, setQ] = useState('');

  // base filter (URL chip 状态) + search query
  const results = useMemo(() => {
    const base = articles.filter((a) => {
      if (disease && a.disease !== disease) return false;
      if (type && a.type !== type) return false;
      return true;
    });
    const trimmed = q.trim();
    if (!trimmed) return base;
    const lower = trimmed.toLowerCase();
    return base
      .map((a) => ({ a, s: score(a, lower) }))
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s)
      .map((x) => x.a);
  }, [articles, disease, type, q]);

  // 按 epdat 分组
  const byDate = new Map<string, Article[]>();
  for (const a of results) {
    const list = byDate.get(a.epdat) ?? [];
    list.push(a);
    byDate.set(a.epdat, list);
  }
  const dateGroups = Array.from(byDate.entries()).sort((a, b) =>
    b[0].localeCompare(a[0]),
  );

  const baseCount = useMemo(
    () =>
      articles.filter((a) => {
        if (disease && a.disease !== disease) return false;
        if (type && a.type !== type) return false;
        return true;
      }).length,
    [articles, disease, type],
  );

  return (
    <>
      <div className="page-toolbar">
        <div className="search-controls">
          <div className="search-input-row">
            <input
              type="search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="搜索标题/摘要/作者/期刊..."
              aria-label="搜索文献"
            />
            {q && (
              <button
                type="button"
                onClick={() => setQ('')}
                aria-label="清空搜索"
              >
                ✕
              </button>
            )}
          </div>
          <p className="search-status">
            {q.trim() ? `匹配 ${results.length} 篇` : `共 ${baseCount} 篇`}
          </p>
        </div>
      </div>

      {dateGroups.length === 0 ? (
        <div className="empty-state">
          <p>暂无符合条件的文献。</p>
        </div>
      ) : (
        dateGroups.map(([date, arts]) => (
          <section key={date} className="date-group">
            <header className="date-group-header">
              <h2 className="date-group-title">
                {formatDate(date)} · {arts.length} 篇
              </h2>
            </header>
            <div className="date-group-list">
              {arts.map((a) => {
                const t = TYPES.find((x) => x.slug === a.type);
                const d = DISEASES.find((x) => x.slug === a.disease);
                const pubmedUrl = `https://pubmed.ncbi.nlm.nih.gov/${a.pmid}/`;
                const showJournal = a.journal_full ?? a.journal;
                return (
                  <article key={a.pmid} className="article-card">
                    <a
                      href={pubmedUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="article-source"
                    >
                      {showJournal}
                    </a>
                    <a href={`/article/${a.pmid}`} className="article-title-link">
                      <h3 className="article-title-zh">{a.title_zh || a.title}</h3>
                      {a.title_zh && a.title_zh !== a.title && (
                        <p className="article-title-en">{a.title}</p>
                      )}
                    </a>
                    <time className="article-date" dateTime={a.epdat}>
                      {a.epdat}
                    </time>
                    <div className="article-tags">
                      {t && <span className="tag tag-type">{t.name_zh}</span>}
                      {d && <span className="tag tag-disease">{d.name_zh}</span>}
                      {a.impact_factor !== null && (
                        <span className="tag tag-if">
                          IF {a.impact_factor.toFixed(1)}
                        </span>
                      )}
                      {a.jcr_quartile && (
                        <span className="tag tag-jcr">{a.jcr_quartile}</span>
                      )}
                      {a.new_talent_quartile && (
                        <span className="tag tag-nt">
                          新锐{a.new_talent_quartile}
                        </span>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          </section>
        ))
      )}
    </>
  );
}