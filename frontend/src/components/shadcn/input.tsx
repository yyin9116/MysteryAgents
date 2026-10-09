import { forwardRef, type InputHTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

/**
 * 夜幕协议 · 输入框（shadcn/ui 风格，接 --ds-* 令牌）
 */
export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      ref={ref}
      className={cn(
        'flex h-10 w-full rounded-lg border border-line bg-white/[0.04] px-3.5 py-2 text-sm text-text-primary',
        'placeholder:text-text-muted/40',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet/50 focus-visible:border-violet/50',
        'disabled:cursor-not-allowed disabled:opacity-50',
        'transition-colors',
        className
      )}
      {...props}
    />
  )
);
Input.displayName = 'Input';
