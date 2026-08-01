/** URL 与 filter 解析工具。 */

import type { DiseaseSlug, TypeSlug } from './types';

export function parseFilter(search: URLSearchParams): {
  disease?: DiseaseSlug;
  type?: TypeSlug;
} {
  const d = search.get('disease');
  const t = search.get('type');
  const validDiseases = ['lung_cancer', 'esophageal', 'mediastinal', 'tracheal', 'chest_wall_injury'];
  const validTypes = ['clinical', 'ai_ml', 'basic_research', 'review', 'guideline'];
  return {
    disease: validDiseases.includes(d ?? '') ? (d as DiseaseSlug) : undefined,
    type: validTypes.includes(t ?? '') ? (t as TypeSlug) : undefined,
  };
}

export function buildArticleUrl(pmid: string): string {
  return `/article/${pmid}`;
}

export function buildTopicUrl(slug: string): string {
  return `/topics/${slug}`;
}

export function buildDiseaseFilterUrl(slug: string | null): string {
  return slug ? `/?disease=${slug}` : '/';
}

export function buildTypeFilterUrl(slug: string | null): string {
  return slug ? `/?type=${slug}` : '/';
}

export function buildCombinedFilterUrl(disease: string | null, type: string | null): string {
  const params = new URLSearchParams();
  if (disease) params.set('disease', disease);
  if (type) params.set('type', type);
  const qs = params.toString();
  return qs ? `/?${qs}` : '/';
}