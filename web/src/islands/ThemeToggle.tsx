import { useEffect, useState } from 'react';

/**
 * 三态暗色切换:system → light → dark → system
 * - 状态存于 localStorage.theme-pref
 * - data-theme 应用于 <html> 元素
 * - 默认 system = 跟随 prefers-color-scheme
 *
 * 注意:BaseLayout 中已经有一段内联脚本在 CSS 加载前设置 data-theme,
 * 因此本组件 mount 时只需要更新 data-theme 与 localStorage 即可,
 * 不会出现 FOUC。
 */

type ThemePref = 'system' | 'light' | 'dark';

function applyTheme(pref: ThemePref) {
  let actual: 'light' | 'dark';
  if (pref === 'system') {
    actual = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  } else {
    actual = pref;
  }
  document.documentElement.setAttribute('data-theme', actual);
}

const ICONS: Record<ThemePref, string> = {
  system: '🖥',
  light: '☀',
  dark: '🌙',
};

const LABELS: Record<ThemePref, string> = {
  system: '跟随系统',
  light: '浅色',
  dark: '深色',
};

export default function ThemeToggle() {
  const [pref, setPref] = useState<ThemePref>('system');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const stored = (localStorage.getItem('theme-pref') as ThemePref | null) ?? 'system';
    setPref(stored);
    setMounted(true);
  }, []);

  // 监听系统偏好变化(当 pref='system' 时实时跟随)
  useEffect(() => {
    if (pref !== 'system') return;
    const mq = matchMedia('(prefers-color-scheme: dark)');
    const handler = () => applyTheme('system');
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [pref]);

  const cycle = () => {
    const next: ThemePref = pref === 'system' ? 'light' : pref === 'light' ? 'dark' : 'system';
    setPref(next);
    localStorage.setItem('theme-pref', next);
    applyTheme(next);
  };

  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={cycle}
      aria-label={`当前主题:${LABELS[pref]},点击切换`}
      title={LABELS[pref]}
      data-active={mounted ? 'true' : 'false'}
    >
      <span className="theme-toggle-icon">{ICONS[pref]}</span>
      <span>{LABELS[pref]}</span>
    </button>
  );
}