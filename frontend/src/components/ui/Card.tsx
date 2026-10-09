import { forwardRef, type HTMLAttributes } from 'react';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** default=常规面板 / strong=加粗描边(悬停或重要) / accent=紫底选中态 */
  variant?: 'default' | 'strong' | 'accent';
}

const variantClasses: Record<NonNullable<CardProps['variant']>, string> = {
  default: 'border-line bg-card',
  strong: 'border-line-strong bg-card',
  accent: 'border-violet bg-violet/10',
};

/**
 * 夜幕协议 · 面板卡片
 * 对应设计系统 16px 圆角、surface 底、subtle/strong 描边
 */
export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ variant = 'default', className = '', ...rest }, ref) => {
    const classes = [
      'rounded-2xl border transition-colors duration-200',
      variantClasses[variant],
      className,
    ]
      .filter(Boolean)
      .join(' ');

    return <div ref={ref} className={classes} {...rest} />;
  },
);

Card.displayName = 'Card';
