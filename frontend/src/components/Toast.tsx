/**
 * Toast Notification Component
 * 
 * 自动消失的提示消息，用于投票开始、淘汰通知等不需要用户确认的消息
 */

import React, { useEffect } from 'react';
import { Vote, UserX, AlertCircle, CheckCircle } from 'lucide-react';

interface ToastProps {
    isOpen: boolean;
    type: 'voting_start' | 'elimination' | 'info' | 'success';
    message: string;
    duration?: number; // 显示时长（毫秒），默认 2000ms
    onClose: () => void;
}

const Toast: React.FC<ToastProps> = ({
    isOpen,
    type,
    message,
    duration = 2000,
    onClose
}) => {
    useEffect(() => {
        if (isOpen) {
            const timer = setTimeout(() => {
                onClose();
            }, duration);
            
            return () => clearTimeout(timer);
        }
    }, [isOpen, duration, onClose]);

    if (!isOpen) return null;

    // 根据类型选择图标和颜色
    const getTypeConfig = () => {
        switch (type) {
            case 'voting_start':
                return {
                    icon: <Vote className="w-6 h-6" />,
                    bgColor: 'bg-blue-500',
                    textColor: 'text-white'
                };
            case 'elimination':
                return {
                    icon: <UserX className="w-6 h-6" />,
                    bgColor: 'bg-red-500',
                    textColor: 'text-white'
                };
            case 'success':
                return {
                    icon: <CheckCircle className="w-6 h-6" />,
                    bgColor: 'bg-green-500',
                    textColor: 'text-white'
                };
            case 'info':
            default:
                return {
                    icon: <AlertCircle className="w-6 h-6" />,
                    bgColor: 'bg-gray-700',
                    textColor: 'text-white'
                };
        }
    };

    const config = getTypeConfig();

    return (
        <div className="fixed top-8 left-1/2 transform -translate-x-1/2 z-50 animate-in fade-in slide-in-from-top-4 duration-300">
            <div className={`${config.bgColor} ${config.textColor} px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-3 min-w-[300px] max-w-[500px]`}>
                <div className="flex-shrink-0">
                    {config.icon}
                </div>
                <p className="text-lg font-medium flex-1">
                    {message}
                </p>
            </div>
        </div>
    );
};

export default Toast;
