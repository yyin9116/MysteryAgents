import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserProfile } from '../types/user';

interface UserStore {
    user: UserProfile | null;
    loading: boolean;
    error: string | null;

    setUser: (user: UserProfile) => void;
    logout: () => void;
}

export const useUserStore = create<UserStore>()(
    persist(
        (set) => ({
            user: null,
            loading: false,
            error: null,

            setUser: (user) => set({ user }),
            logout: () => set({ user: null }),
        }),
        {
            name: 'user-storage',
        }
    )
);
