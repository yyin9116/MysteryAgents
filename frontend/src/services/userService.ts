import api from './api';
import type { UserProfile, CreateProfileRequest, MBTIType } from '../types/user';

export const userService = {
    createProfile: async (data: CreateProfileRequest): Promise<UserProfile> => {
        const response = await api.post('/api/user/profile', data);
        return response.data.profile;
    },

    getMBTITypes: async (): Promise<Record<MBTIType, string>> => {
        const response = await api.get('/api/user/mbti-types');
        return response.data.mbti_types;
    },

    updateMBTI: async (userId: string, mbtiType: MBTIType): Promise<UserProfile> => {
        const response = await api.put(`/api/user/profile/${userId}/mbti?mbti_type=${mbtiType}`);
        return response.data;
    },
};

export default userService;
