/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { AnimatePresence } from 'motion/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from './components/ui/sonner';
import { AppLayout } from './components/layout/AppLayout';
import { Login } from './pages/Login';
import { Onboarding } from './pages/Onboarding';
import { Overview } from './pages/Overview';
import { Transactions } from './pages/Transactions';
import { Analytics } from './pages/Analytics';
import { Categories } from './pages/Categories';
import { useAuthStore } from './store/authStore';
import { useSSE } from './hooks/useSSE';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,   // 5 min — don't refetch on every route change
      gcTime:    1000 * 60 * 10,   // keep cache 10 min after component unmounts
      retry: 1,
      retryDelay: 500,             // don't wait 1s between retries
      refetchOnWindowFocus: false, // avoid surprise refetch when tab regains focus
    },
  },
});

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (user && !user.isOnboarded && window.location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />;
  }

  return <>{children}</>;
}

function AppContent() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  // <<< FIX: always call the hook — React hooks must never be called conditionally.
  // useSSE internally returns early when there is no token, so calling it
  // unconditionally is safe and doesn't open a connection when logged out. >>>
  useSSE('/api/sse/stream');

  const location = useLocation();

  return (
    <AnimatePresence mode="wait">
      <Routes location={location} key={location.pathname}>
        <Route path="/login" element={<Login />} />
        <Route 
          path="/onboarding" 
          element={
            <ProtectedRoute>
              <Onboarding />
            </ProtectedRoute>
          } 
        />
        <Route 
          path="/" 
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<Overview />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="categories-budgets" element={<Categories />} />
        </Route>
      </Routes>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppContent />
        <Toaster position="top-right" />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
