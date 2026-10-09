import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';

interface Props {
    children: ReactNode;
}

interface State {
    error: Error | null;
}

/**
 * 全局错误边界：任何未捕获的渲染错误只显示局部提示与恢复入口，
 * 不再让整页蓝屏。开发模式保留完整堆栈方便定位。
 */
export default class ErrorBoundary extends Component<Props, State> {
    state: State = { error: null };

    static getDerivedStateFromError(error: Error): State {
        return { error };
    }

    componentDidCatch(error: Error, info: ErrorInfo) {
        // 保留到控制台，便于排查
        console.error('[ErrorBoundary]', error, info.componentStack);
    }

    private handleReload = () => {
        this.setState({ error: null });
        window.location.reload();
    };

    private handleBack = () => {
        this.setState({ error: null });
        window.location.hash = '';
        window.location.href = '/';
    };

    render() {
        const { error } = this.state;
        if (!error) return this.props.children;

        return (
            <div className="flex min-h-screen items-center justify-center bg-[#0D0B14] p-6">
                <div className="w-full max-w-lg rounded-2xl border border-red-500/30 bg-[#171420] p-8 text-center">
                    <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-500/15">
                        <AlertTriangle className="text-red-400" size={24} />
                    </div>
                    <h1 className="mb-2 text-lg font-bold text-text-primary">页面出了点问题</h1>
                    <p className="mb-4 text-sm leading-6 text-text-secondary/80">
                        界面渲染遇到错误，其他页面仍可正常使用。
                    </p>
                    {import.meta.env.DEV && (
                        <pre className="mb-5 max-h-40 overflow-auto rounded-lg border border-line bg-black/40 p-3 text-left text-xs leading-5 text-red-300">
                            {error.message}
                            {'\n'}
                            {error.stack?.split('\n').slice(1, 6).join('\n')}
                        </pre>
                    )}
                    <div className="flex justify-center gap-3">
                        <button
                            onClick={this.handleReload}
                            className="flex items-center gap-2 rounded-xl bg-gold px-5 py-2.5 text-sm font-semibold text-[#2B2836] transition-all hover:brightness-110 active:scale-95"
                        >
                            <RotateCcw size={15} />
                            重试
                        </button>
                        <button
                            onClick={this.handleBack}
                            className="rounded-xl border border-line px-5 py-2.5 text-sm font-medium text-text-secondary transition-all hover:border-violet/40 hover:text-violet active:scale-95"
                        >
                            返回首页
                        </button>
                    </div>
                </div>
            </div>
        );
    }
}
