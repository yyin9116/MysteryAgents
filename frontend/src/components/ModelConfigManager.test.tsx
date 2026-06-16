import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { ModelConfigManager } from './ModelConfigManager';
import { useSettingsStore } from '../store/settingsStore';

// Mock Lucide icons
vi.mock('lucide-react', () => ({
    Search: () => <div data-testid="search-icon" />,
    Plus: () => <div data-testid="plus-icon" />,
    Copy: () => <div data-testid="copy-icon" />,
    Trash2: () => <div data-testid="trash-icon" />,
    Save: () => <div data-testid="save-icon" />,
    Play: () => <div data-testid="play-icon" />,
    Download: () => <div data-testid="download-icon" />,
    Upload: () => <div data-testid="upload-icon" />,
    BarChart2: () => <div data-testid="chart-icon" />,
    AlertCircle: () => <div data-testid="alert-icon" />,
    CheckCircle2: () => <div data-testid="check-icon" />,
}));

// Mock the store
vi.mock('../store/settingsStore', () => ({
    useSettingsStore: vi.fn(),
}));

const mockConfigs = [
    {
        id: '1',
        name: 'GPT-4',
        provider: 'openai',
        model: 'gpt-4',
        temperature: 0.7,
        max_tokens: 2000,
        extra_params: {},
    },
    {
        id: '2',
        name: 'Claude 3',
        provider: 'anthropic',
        model: 'claude-3',
        temperature: 0.5,
        max_tokens: 4000,
        extra_params: {},
    },
];

describe('ModelConfigManager', () => {
    const mockFetch = vi.fn();
    const mockCreate = vi.fn();
    const mockUpdate = vi.fn();
    const mockDelete = vi.fn();
    const mockExport = vi.fn();
    const mockImport = vi.fn();
    const mockGetUsage = vi.fn().mockResolvedValue({
        summary: { total_tokens: 0, total_cost: 0, call_count: 0 },
        aggregates: [],
    });

    beforeEach(() => {
        vi.clearAllMocks();
        (useSettingsStore as any).mockReturnValue({
            modelConfigs: mockConfigs,
            modelConfigsLoading: false,
            fetchModelConfigs: mockFetch,
            createModelConfig: mockCreate,
            updateModelConfig: mockUpdate,
            deleteModelConfig: mockDelete,
            exportModelConfigs: mockExport,
            importModelConfigs: mockImport,
            getUsageStats: mockGetUsage,
        });
    });

    afterEach(() => {
        cleanup();
    });

    it('renders the config list', () => {
        render(<ModelConfigManager />);
        expect(screen.getAllByText('GPT-4')[0]).toBeTruthy();
        expect(screen.getAllByText('Claude 3')[0]).toBeTruthy();
    });

    it('filters configs based on search term', async () => {
        render(<ModelConfigManager />);
        const searchInputs = screen.getAllByPlaceholderText('搜索配置...');
        fireEvent.change(searchInputs[0], { target: { value: 'GPT' } });
        
        expect(screen.getByText('GPT-4')).toBeTruthy();
        expect(screen.queryByText('Claude 3')).toBeNull();
    });

    it('shows editor when a config is selected', async () => {
        render(<ModelConfigManager />);
        fireEvent.click(screen.getAllByText('GPT-4')[0]);
        
        expect(screen.getByDisplayValue('GPT-4')).toBeTruthy();
        expect(screen.getByDisplayValue('gpt-4')).toBeTruthy();
    });

    it('switches to creation mode when add button is clicked', async () => {
        render(<ModelConfigManager />);
        const addButtons = screen.getAllByTitle('添加新配置');
        fireEvent.click(addButtons[0]);
        
        expect(screen.getByText('新建配置')).toBeTruthy();
        expect(screen.getByDisplayValue('新配置')).toBeTruthy();
    });

    it('calls deleteModelConfig when delete button is clicked', async () => {
        // Mock window.confirm
        window.confirm = vi.fn().mockReturnValue(true);
        
        render(<ModelConfigManager />);
        const deleteButtons = screen.getAllByTitle('删除');
        fireEvent.click(deleteButtons[0]);
        
        expect(mockDelete).toHaveBeenCalledWith('1');
    });
});
