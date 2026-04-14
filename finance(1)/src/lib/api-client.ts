/**
 * <<< INTEGRATION: replaced mock data with real FastAPI calls >>>
 *
 * All field mapping between the frontend camelCase types and the backend
 * snake_case JSON lives here.  No page or component changes are needed.
 *
 * Backend base paths (proxied through Vite in dev, direct in prod):
 *   POST   /api/auth/login
 *   POST   /api/auth/register
 *   GET    /api/auth/me
 *   GET    /api/transactions
 *   POST   /api/transactions
 *   DELETE /api/transactions/:id
 *   GET    /api/categories
 *   POST   /api/categories
 */

import { http } from './api';
import type { Transaction, Category } from '../types';

// ── Colour palette assigned by index (backend has no colour field) ─────────
const PALETTE = [
  '#4f46e5', '#ef4444', '#f97316', '#8b5cf6',
  '#06b6d4', '#10b981', '#f59e0b', '#ec4899',
];
function paletteColor(index: number): string {
  return PALETTE[index % PALETTE.length];
}

// ── Backend response shapes (snake_case) ───────────────────────────────────

interface ApiTransaction {
  id: string;
  amount: string | number;   // Decimal comes as string from FastAPI JSON
  type: 'income' | 'expense';
  category_id: string | null;
  date: string;
  description: string | null;
  source: string;
  version: number;
  created_at: string;
  updated_at: string;
}

interface ApiCategory {
  id: string;
  name: string;
  type: 'income' | 'expense';
  is_default: boolean;
  created_at: string;
}

interface ApiTransactionList {
  items: ApiTransaction[];
  total: number;
  page: number;
  limit: number;
}

// ── Mappers ────────────────────────────────────────────────────────────────

function toTransaction(raw: ApiTransaction): Transaction {
  return {
    id: raw.id,
    amount: Number(raw.amount),
    type: raw.type,
    categoryId: raw.category_id ?? '',
    date: raw.date,
    description: raw.description ?? undefined,
  };
}

function toCategory(raw: ApiCategory, index: number): Category {
  return {
    id: raw.id,
    name: raw.name,
    type: raw.type,
    color: paletteColor(index),
    // budgetLimit comes from a separate /api/budgets endpoint;
    // omitting here keeps the integration minimal — backend alerts still work
    budgetLimit: undefined,
  };
}

// ── Public API surface (same shape as the old mock) ────────────────────────

export const api = {
  // ── Transactions ──────────────────────────────────────────────────────────

  getTransactions: async (): Promise<Transaction[]> => {
    const data = await http.get<ApiTransactionList>(
      '/api/transactions?limit=200&page=1',
    );
    return data.items
      .map(toTransaction)
      .sort((a, b) => new Date(b.date).getTime() - new Date(a.date).getTime());
  },

  addTransaction: async (
    data: Omit<Transaction, 'id'>,
  ): Promise<Transaction> => {
    const payload = {
      amount: data.amount,
      type: data.type,
      category_id: data.categoryId || null,
      date: data.date,
      description: data.description ?? null,
      source: 'web' as const,       // required by backend, not in frontend type
    };
    const created = await http.post<ApiTransaction>('/api/transactions', payload);
    return toTransaction(created);
  },

  deleteTransaction: async (id: string): Promise<void> => {
    await http.delete(`/api/transactions/${id}`);
  },

  // ── Categories ────────────────────────────────────────────────────────────

  getCategories: async (): Promise<Category[]> => {
    const data = await http.get<ApiCategory[]>('/api/categories');
    return data.map(toCategory);
  },

  addCategory: async (data: Omit<Category, 'id'>): Promise<Category> => {
    const payload = { name: data.name, type: data.type };
    const created = await http.post<ApiCategory>('/api/categories', payload);
    return toCategory(created, 0);
  },
};
