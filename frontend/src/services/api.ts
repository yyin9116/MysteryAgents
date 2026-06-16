import axios from 'axios';

const DEFAULT_API_BASE_URL = 'http://localhost:8000';

const trimTrailingSlash = (value: string) => value.replace(/\/$/, '');

export const getApiBaseUrl = () => {
    const configured = import.meta.env.VITE_API_BASE_URL?.trim();
    if (!configured) {
        return DEFAULT_API_BASE_URL;
    }
    return trimTrailingSlash(configured);
};

export const buildApiUrl = (path: string) => {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${getApiBaseUrl()}${normalizedPath}`;
};

export const api = axios.create({
    baseURL: getApiBaseUrl(),
    headers: {
        'Content-Type': 'application/json',
    },
});

export default api;
