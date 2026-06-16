import React, { useMemo } from 'react';
import type { UsageAggregate } from '../types/usage';

interface UsageChartProps {
    data: UsageAggregate[];
    type: 'tokens' | 'cost' | 'count';
    height?: number;
    color?: string;
}

export const UsageChart: React.FC<UsageChartProps> = ({
    data,
    type,
    height = 150,
    color = 'bg-purple-500',
}) => {
    const maxValue = useMemo(() => {
        if (!data.length) return 0;
        return Math.max(...data.map((d) => (type === 'tokens' ? d.total_tokens : type === 'cost' ? d.total_cost : d.call_count)));
    }, [data, type]);

    if (!data.length) {
        return (
            <div className="flex items-center justify-center h-full text-gray-400 text-sm">
                No usage data available
            </div>
        );
    }

    const formatValue = (value: number) => {
        if (type === 'cost') return `$${value.toFixed(4)}`;
        return value.toLocaleString();
    };

    const formatLabel = (label: string) => {
        // Simple formatter, can be improved based on date format
        const date = new Date(label);
        if (!isNaN(date.getTime())) {
            return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
        }
        return label;
    };

    return (
        <div className="w-full" style={{ height }}>
            <div className="flex items-end h-[85%] gap-1">
                {data.map((item, index) => {
                    const value = type === 'tokens' ? item.total_tokens : type === 'cost' ? item.total_cost : item.call_count;
                    const heightPercent = maxValue > 0 ? (value / maxValue) * 100 : 0;
                    
                    return (
                        <div key={index} className={`relative flex-1 group ${color} rounded-t-sm min-w-[4px]`} style={{ height: `${heightPercent}%` }}>
                            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-1 bg-gray-800 text-white text-xs rounded opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                                <div className="font-bold">{formatLabel(item.group_value)}</div>
                                <div>{formatValue(value)}</div>
                            </div>
                        </div>
                    );
                })}
            </div>
            <div className="flex justify-between mt-2 text-xs text-gray-500 border-t pt-1">
                 <span>{formatLabel(data[0].group_value)}</span>
                 <span>{formatLabel(data[data.length - 1].group_value)}</span>
            </div>
        </div>
    );
};
