import { forwardRef, type ButtonHTMLAttributes } from 'react';

export type ButtonVariant = 'primary' | 'gold' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** 占满一行（用于表单底部主操作） */
  block?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: 'bg-violet text-white hover:brightness-110',
  gold: 'bg-gold text-[#171424] hover:brightness-105',
  ghost: 'border border-line-strong text-text hover:border-white/40',
  danger: 'border border-danger/60 text-danger hover:bg-danger/10',
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2.5 text-sm',
  lg: 'px-6 py-3.5 text-base',
};

/**
 * 夜幕协议 · 按钮
 * primary=紫(主动作) / gold=金(关键确认) / ghost=描边(次级) / danger=危险(删除/结束)
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', block = false, className = '', type = 'button', ...rest }, ref) => {
    const classes = [
      'inline-flex items-center justify-center gap-2 rounded-xl font-medium',
      'transition-all duration-200 cursor-pointer select-none',
      'disabled:opacity-50 disabled:pointer-events-none',
      variantClasses[variant],
      sizeClasses[size],
      block ? 'w-full' : '',
      className,
    ]
      .filter(Boolean)
      .join(' ');

    return <button ref={ref} type={type} className={classes} {...rest} />;
  },
);

Button.displayName = 'Button';
