import { forwardRef, type TextareaHTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

/**
 * 夜幕协议 · 多行文本框（shadcn/ui 风格）
 */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        'flex min-h-[70px] w-full rounded-lg border border-line bg-white/[0.04] px-3.5 py-2.5 text-sm text-text-primary',
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
Textarea.displayName = 'Textarea';
