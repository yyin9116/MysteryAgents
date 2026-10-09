import { Moon, Sun } from 'lucide-react';
import { useTheme } from '../hooks/useTheme';

/**
 * 夜幕协议 · 昼夜切换按钮
 * 写入 html[data-theme]，令牌层（design-tokens.css）即时换肤
 */
export function ThemeToggle({ className = '' }: { className?: string }) {
  const { theme, toggle } = useTheme();
  const isDay = theme === 'day';
  const label = isDay ? '切换到夜间模式' : '切换到日间模式';

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className={`flex h-9 w-9 items-center justify-center rounded-xl border border-line text-text-muted transition-all hover:border-line-strong hover:text-gold ${className}`}
    >
      {isDay ? <Moon size={18} aria-hidden="true" /> : <Sun size={18} aria-hidden="true" />}
    </button>
  );
}
