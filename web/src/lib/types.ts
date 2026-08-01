/** Article 单条记录(对应 snapshot JSON 中的单篇 article)。 */
export interface Article {
  pmid: string;
  title: string;
  title_zh: string;
  abstract: string | null;
  abstract_zh: string | null;
  authors: string[];
  affiliations: (string | null)[];
  journal: string;
  journal_full: string | null;
  journal_abbr: string | null;
  doi: string | null;
  publication_types: string[];
  pubdate: string | null;
  epdat: string;
  fetched_at: string;
  disease: string;
  type: string;
  impact_factor: number | null;
  jcr_quartile: string | null;
  new_talent_quartile: string | null;
  matched_jcr: string | null;
  llm_model: string | null;
  llm_excluded: number;
  llm_needs_review: number;
}

/** 单日 snapshot。 */
export interface DailySnapshot {
  date: string;
  generated_at: string;
  article_count: number;
  articles: Article[];
}

/** 病种常量。 */
export const DISEASES = [
  { slug: 'lung_cancer', name_zh: '肺癌' },
  { slug: 'esophageal', name_zh: '食管癌' },
  { slug: 'mediastinal', name_zh: '纵隔肿瘤' },
  { slug: 'tracheal', name_zh: '气管疾病' },
  { slug: 'chest_wall_injury', name_zh: '气胸·外伤·胸壁' },
] as const;

/** 类型常量。 */
export const TYPES = [
  { slug: 'clinical', name_zh: '临床研究' },
  { slug: 'ai_ml', name_zh: 'AI/ML' },
  { slug: 'basic_research', name_zh: '基础研究' },
  { slug: 'review', name_zh: '综述Meta' },
  { slug: 'guideline', name_zh: '指南共识' },
] as const;

export type DiseaseSlug = (typeof DISEASES)[number]['slug'];
export type TypeSlug = (typeof TYPES)[number]['slug'];