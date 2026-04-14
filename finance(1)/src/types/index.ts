export type TransactionType = 'income' | 'expense';

export interface Category {
  id: string;
  name: string;
  type: TransactionType;
  color: string;
  budgetLimit?: number;
}

export interface Transaction {
  id: string;
  amount: number;
  type: TransactionType;
  categoryId: string;
  date: string;
  description?: string;
}

export interface User {
  id: string;
  email: string;
  name: string;
  isOnboarded: boolean;
}
