import create from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware/persist';
import { api, authApi } from '../services/api';

export interface User {
  user_id: string;
  username: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  is_demo: boolean;
  last_login_at?: string;
}

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  login: (credentials: { username: string; password: string }) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
}

export const useAuth = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,

      login: async (credentials) => {
        const response = await authApi.login(credentials);
        const { access_token, user } = response.data;
        localStorage.setItem('access_token', access_token);
        localStorage.setItem('user_role', user.role);
        set({ user, token: access_token, isAuthenticated: true });
      },

      logout: () => {
        authApi.logout();
        set({ user: null, token: null, isAuthenticated: false });
      },

      checkAuth: async () => {
        const token = localStorage.getItem('access_token');
        if (token) {
          try {
            const response = await authApi.getMe();
            set({ user: response.data, token, isAuthenticated: true });
          } catch (error) {
            localStorage.removeItem('access_token');
            set({ user: null, token: null, isAuthenticated: false });
          }
        }
      },
    }),
    { name: 'vtr-auth', storage: createJSONStorage(localStorage) }
  )
);