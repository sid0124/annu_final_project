import React, { createContext, useContext, useState, useEffect } from 'react';
import { useAuth } from './context/auth-context';

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
  const { user, isAuthenticated, login, logout, checkAuth } = useAuth();

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, login, logout }}>
      {children}
  </AuthContext.Provider>
);
};

export const useAuthContext = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuthContext must be used within AuthProvider');
  }
  return context;
};

export const AuthContext = createContext({
  user: null,
  isAuthenticated: false,
  login: () => {},
  logout: () => {},
});