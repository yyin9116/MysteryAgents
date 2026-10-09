import { forwardRef, type LabelHTMLAttributes } from 'react';
import { cn } from '../../lib/utils';

/**
 * 夜幕协议 · 表单标签（shadcn/ui 风格）
 */
export const Label = forwardRef<HTMLLabelElement, LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label
      ref={ref}
      className={cn(
        'text-sm font-semibold text-text-secondary leading-none select-none',
        'peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
        className
      )}
      {...props}
    />
  )
);
Label.displayName = 'Label';
