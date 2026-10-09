import type { HTMLAttributes } from 'react';

export type BadgeTone =
  | 'neutral'
  | 'gold'
  | 'violet'
  | 'success'
  | 'danger'
  | 'info'
  | 'wolf'
  | 'seer'
  | 'witch'
  | 'guard'
  | 'civilian'
  | 'undercover';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  /** 显示前缀圆点（角色徽章常用） */
  dot?: boolean;
}

const toneClasses: Record<BadgeTone, string> = {
  neutral: 'text-text-muted border-line-strong',
  gold: 'text-gold border-gold/50',
  violet: 'text-violet border-violet/50',
  success: 'text-success border-success/50',
  danger: 'text-danger border-danger/50',
  info: 'text-info border-info/50',
  wolf: 'text-role-wolf border-role-wolf/50',
  seer: 'text-role-seer border-role-seer/50',
  witch: 'text-role-witch border-role-witch/50',
  guard: 'text-role-guard border-role-guard/50',
  civilian: 'text-role-civilian border-role-civilian/50',
  undercover: 'text-role-undercover border-role-undercover/50',
};

const dotClasses: Record<BadgeTone, string> = {
  neutral: 'bg-text-muted',
  gold: 'bg-gold',
  violet: 'bg-violet',
  success: 'bg-success',
  danger: 'bg-danger',
  info: 'bg-info',
  wolf: 'bg-role-wolf',
  seer: 'bg-role-seer',
  witch: 'bg-role-witch',
  guard: 'bg-role-guard',
  civilian: 'bg-role-civilian',
  undercover: 'bg-role-undercover',
};

/**
 * 夜幕协议 · 徽章
 * tone 支持语义状态与六种角色色，dot 显示前缀圆点
 */
export function Badge({ tone = 'neutral', dot = false, className = '', ...rest }: BadgeProps) {
  const classes = [
    'inline-flex items-center gap-1.5 rounded-[10px] border px-2.5 py-1',
    'text-xs leading-none whitespace-nowrap',
    toneClasses[tone],
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <span className={classes} {...rest}>
      {dot && <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${dotClasses[tone]}`} />}
      {rest.children}
    </span>
  );
}
