import { useCallback, useEffect, useState } from 'react';

export type Theme = 'night' | 'day';

const STORAGE_KEY = 'app-theme';

/**
 * 夜幕协议 · 主题切换
 * night 为默认；day 映射到 design-tokens.css 的 [data-theme="day"] 令牌组
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(() => {
    try {
      return (localStorage.getItem(STORAGE_KEY) as Theme) ?? 'night';
    } catch {
      return 'night';
    }
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'day') {
      root.dataset.theme = 'day';
    } else {
      delete root.dataset.theme;
    }
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* localStorage 不可用时静默降级 */
    }
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme((current) => (current === 'night' ? 'day' : 'night'));
  }, []);

  return { theme, toggle };
}
