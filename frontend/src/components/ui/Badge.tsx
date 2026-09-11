import React from 'react';
import { RiskLevel } from '../../types/warehouse';

interface BadgeProps {
  level?: RiskLevel | string;
  children?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
}

export const RiskBadge: React.FC<BadgeProps> = ({ level = 'GREEN', children, size = 'md' }) => {
  const normalized = (typeof level === 'string' ? level.toUpperCase() : 'GREEN') as RiskLevel;

  const styles = {
    GREEN: 'bg-emerald-50 text-emerald-700 border-emerald-200',
    YELLOW: 'bg-amber-50 text-amber-700 border-amber-200',
    ORANGE: 'bg-orange-50 text-orange-700 border-orange-200',
    RED: 'bg-rose-50 text-rose-700 border-rose-200',
  }[normalized] || 'bg-slate-50 text-slate-700 border-slate-200';

  const dotColor = {
    GREEN: 'bg-emerald-500',
    YELLOW: 'bg-amber-500',
    ORANGE: 'bg-orange-500',
    RED: 'bg-rose-500',
  }[normalized] || 'bg-slate-400';

  const sizeClasses = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-xs font-semibold px-2.5 py-1',
    lg: 'text-sm font-semibold px-3 py-1.5',
  }[size];

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border ${styles} ${sizeClasses}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
      {children || normalized}
    </span>
  );
};
