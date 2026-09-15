import React from 'react';
import { Card, CardContent, CardHeader, Button } from './styles';
import { Loader2, LogOut, Shield, Users, BarChart3, Clock } from 'lucide-react';
import { useAuth } from './context/auth-context';
import { useDispatch } from 'react-redux';
import { logout } from '../store';

export const Header = () => {
  const { user, isAuthenticated, logout } = useAuth();

  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold text-gray-900">
            <svg className="inline w-6 h-6 text-blue-600" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 7v6l4 2-4 2v-6l-4-2-4 2v-6L12 7zM12 3v2m0 12v2M4.93 4.93l2.83 2.83a1 1 0 0 1-1.42 0L2 10v2h2l2.93-1.93a1 1 0 0 1 1.42 0l2.83 2.83a1 1 0 0 1-1.42 0L2 18v2h2l2.93 1.93a1 1 0 0 1 1.42 0l2.83-2.83a1 1 0 0 1 0-1.42L6.78 10H2c-1.1 0-2-1-2-2v-5a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v5z" />
            </svg>
            VTR-Agent
          </h1>
        </div>

        <div className="hidden md:flex items-center gap-4">
          <span className="text-sm text-gray-600">
            Welcome, {user?.full_name || user?.username}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={logout}
            className="flex items-center gap-1"
          >
            <LogOut className="h-4 w-4" />Sign Out
          </Button>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={checkAuth}
          className="hidden md:flex items-center gap-1"
        >
          <Shield className="h-4 w-4" />Invisible
        </Button>
      </div>
    </header>
  );
};

const checkAuth = async () => {
  // Trigger auth check from store
};