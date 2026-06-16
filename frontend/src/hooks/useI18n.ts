import { useSettingsStore } from '../store/settingsStore';
import { translations } from '../utils/i18n';

export const useI18n = () => {
    const language = useSettingsStore((state) => state.language);

    // Create a helper to access nested keys
    const t = translations[language];

    return { t, language };
};
