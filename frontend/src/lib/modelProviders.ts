/**
 * LLM 服务商协议元数据。
 * 声明这张表之后，表单的 base_url 预填、api_key 必填提示、模型建议列表
 * 全部由映射驱动，无需在组件里手写切换逻辑。
 */

export interface ProviderMeta {
  /** 展示名 */
  label: string;
  /** OpenAI 兼容默认端点（litellm 走 api_base） */
  defaultBaseUrl: string;
  /** 是否必须提供 api_key（环境变量兜底除外） */
  keyRequired: boolean;
  /** api_key 输入框 placeholder */
  keyPlaceholder: string;
  /** 模型建议列表（渲染为 datalist，仍允许自由输入） */
  models: string[];
  /** 补充说明（渲染在下方的 hint） */
  hint?: string;
  /** 是否为推荐服务商（多模型对局实验首选） */
  recommended?: boolean;
}

/** 推荐服务商：不同模型与思考模式可模拟不同能力的玩家 */
export const RECOMMENDED_PROVIDER = 'opencode';

export const PROVIDER_META: Record<string, ProviderMeta> = {
  openai: {
    label: 'OpenAI',
    defaultBaseUrl: 'https://api.openai.com/v1',
    keyRequired: true,
    keyPlaceholder: 'sk-...',
    models: ['gpt-4o', 'gpt-4o-mini', 'gpt-5.5', 'o3-mini'],
    hint: 'GPT-5 系列模型仅支持 temperature=1。',
  },
  opencode: {
    label: 'OpenCode Go',
    defaultBaseUrl: 'https://opencode.ai/zen/go/v1',
    keyRequired: true,
    keyPlaceholder: 'OpenCode Console 的 API Key',
    models: [
      'gpt-5.6-luna',
      'gpt-6-luna',
      'glm-5.3-flash',
      'glm-5.3',
      'kimi-k3',
      'kimi-k2.7-code',
      'deepseek-v4.1-flash',
      'deepseek-v4-pro',
      'qwen3.8-max',
      'qwen3.8-flash',
      'minimax-m3',
      'grok-4.7',
    ],
    hint: '推荐：多模型对局实验首选。Go 订阅内含十余种模型，可用不同模型/思考档位模拟不同能力的玩家；必需的会话头与 Responses 协议由后端自动适配。',
    recommended: true,
  },
  anthropic: {
    label: 'Anthropic',
    defaultBaseUrl: 'https://api.anthropic.com/v1',
    keyRequired: true,
    keyPlaceholder: 'sk-ant-...',
    models: ['claude-sonnet-4-5', 'claude-3-5-sonnet-latest', 'claude-3-5-haiku-latest'],
  },
  google: {
    label: 'Google Gemini',
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta',
    keyRequired: true,
    keyPlaceholder: 'AIza...',
    models: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.0-flash'],
  },
  deepseek: {
    label: 'DeepSeek',
    defaultBaseUrl: 'https://api.deepseek.com/v1',
    keyRequired: true,
    keyPlaceholder: 'sk-...',
    models: ['deepseek-chat', 'deepseek-reasoner'],
  },
  alibaba: {
    label: 'Alibaba DashScope',
    defaultBaseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    keyRequired: true,
    keyPlaceholder: 'sk-...',
    models: ['qwen-max', 'qwen-plus', 'qwen-turbo'],
  },
  ollama: {
    label: 'Ollama（本地）',
    defaultBaseUrl: 'http://localhost:11434/v1',
    keyRequired: false,
    keyPlaceholder: '本地服务通常无需 key',
    models: ['llama3.1', 'qwen2.5', 'mistral'],
    hint: '本地部署无需 api_key，确认服务已启动即可。',
  },
};

/** 未知 provider 的兜底元数据 */
export const FALLBACK_META: ProviderMeta = {
  label: '自定义',
  defaultBaseUrl: '',
  keyRequired: true,
  keyPlaceholder: 'sk-...',
  models: [],
};

export const getProviderMeta = (provider?: string | null): ProviderMeta =>
  (provider && PROVIDER_META[provider]) || FALLBACK_META;

/**
 * 从已保存配置里挑推荐项：优先推荐服务商（OpenCode Go），回落到列表第一个。
 * 供首页 / 模型选择器 / 对局配置共用，保证「推荐配置」的一致口径。
 */
export const pickPreferredModelConfig = <T extends { provider?: string | null }>(
  configs: T[],
): T | null => {
  if (!configs.length) return null;
  return configs.find((c) => (c.provider ?? '') === RECOMMENDED_PROVIDER) || configs[0];
};

/**
 * 判断 base_url 是否可以安全地自动切换：
 * 当前值为空、或正好等于其它 provider 的默认值时才覆盖，避免吞掉用户自定义端点。
 */
export const shouldAutoFillBaseUrl = (current: string | undefined | null): boolean => {
  const value = (current ?? '').trim();
  if (!value) return true;
  return Object.values(PROVIDER_META).some((meta) => meta.defaultBaseUrl === value);
};
