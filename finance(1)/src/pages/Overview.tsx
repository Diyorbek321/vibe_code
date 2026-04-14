import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { ArrowDownRight, ArrowUpRight, Plus, Wallet, Receipt } from 'lucide-react';
import { useTransactions } from '../hooks/useTransactions';
import { formatUZS, formatDate } from '../lib/formatters';
import { TransactionForm } from '../components/forms/TransactionForm';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { PageTransition } from '../components/layout/PageTransition';
import { startOfMonth, endOfMonth, subMonths, isWithinInterval } from 'date-fns';
import { Transaction } from '../types';
import { EmptyState } from '../components/ui/empty-state';

function PercentBadge({ value, invert = false }: { value: number, invert?: boolean }) {
  if (!isFinite(value) || isNaN(value)) return null;
  
  const isPositive = value > 0;
  const isNeutral = value === 0;
  const isGood = invert ? !isPositive : isPositive;
  
  const Icon = isPositive ? ArrowUpRight : ArrowDownRight;
  
  let colorClass = 'text-slate-500';
  if (!isNeutral) {
    colorClass = isGood ? 'text-emerald-600' : 'text-rose-600';
  }

  return (
    <p className={`text-xs flex items-center mt-1 ${colorClass}`}>
      {!isNeutral && <Icon className="w-3 h-3 mr-1" />}
      {isPositive ? '+' : ''}{value.toFixed(1)}% o'tgan oyga nisbatan
    </p>
  );
}

export function Overview() {
  const { data: transactions = [], isLoading } = useTransactions();
  const [isAddOpen, setIsAddOpen] = useState(false);

  const now = new Date();
  const currentMonthStart = startOfMonth(now);
  const currentMonthEnd = endOfMonth(now);
  const lastMonthStart = startOfMonth(subMonths(now, 1));
  const lastMonthEnd = endOfMonth(subMonths(now, 1));

  const currentMonthTx = transactions.filter(t => 
    isWithinInterval(new Date(t.date), { start: currentMonthStart, end: currentMonthEnd })
  );
  const lastMonthTx = transactions.filter(t => 
    isWithinInterval(new Date(t.date), { start: lastMonthStart, end: lastMonthEnd })
  );

  const calculateStats = (txs: Transaction[]) => {
    const income = txs.filter(t => t.type === 'income').reduce((sum, t) => sum + t.amount, 0);
    const expense = txs.filter(t => t.type === 'expense').reduce((sum, t) => sum + t.amount, 0);
    return { income, expense, net: income - expense };
  };

  const currentStats = calculateStats(currentMonthTx);
  const lastStats = calculateStats(lastMonthTx);

  const calculatePercentage = (current: number, previous: number) => {
    if (previous === 0) return current > 0 ? 100 : (current < 0 ? -100 : 0);
    return ((current - previous) / Math.abs(previous)) * 100;
  };

  const incomePercent = calculatePercentage(currentStats.income, lastStats.income);
  const expensePercent = calculatePercentage(currentStats.expense, lastStats.expense);
  const netPercent = calculatePercentage(currentStats.net, lastStats.net);

  const recentTransactions = transactions.slice(0, 5);

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Yuklanmoqda...</div>;
  }

  return (
    <PageTransition className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Umumiy holat</h1>
          <p className="text-sm text-slate-500">Joriy oydagi moliyaviy ko'rsatkichlar</p>
        </div>
        
        <Dialog open={isAddOpen} onOpenChange={setIsAddOpen}>
          <DialogTrigger asChild>
            <Button className="bg-indigo-600 hover:bg-indigo-700">
              <Plus className="w-4 h-4 mr-2" />
              Yangi qo'shish
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Yangi tranzaksiya</DialogTitle>
            </DialogHeader>
            <TransactionForm onSuccess={() => setIsAddOpen(false)} />
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Sof foyda</CardTitle>
            <Wallet className="w-4 h-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">{formatUZS(currentStats.net)}</div>
            <PercentBadge value={netPercent} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Daromad</CardTitle>
            <ArrowUpRight className="w-4 h-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">{formatUZS(currentStats.income)}</div>
            <PercentBadge value={incomePercent} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Xarajat</CardTitle>
            <ArrowDownRight className="w-4 h-4 text-rose-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-slate-900">{formatUZS(currentStats.expense)}</div>
            <PercentBadge value={expensePercent} invert />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>So'nggi tranzaksiyalar</CardTitle>
        </CardHeader>
        <CardContent>
          {recentTransactions.length === 0 ? (
            <EmptyState 
              icon={Receipt}
              title="Hali ma'lumot yo'q"
              description="Telegram botga yozing yoki shu yerdan qo'shing"
              action={
                <Button onClick={() => setIsAddOpen(true)} variant="outline" className="mt-2">
                  <Plus className="w-4 h-4 mr-2" />
                  Yangi qo'shish
                </Button>
              }
            />
          ) : (
            <div className="divide-y divide-slate-100">
              {recentTransactions.map((t) => (
                <div key={t.id} className="py-3 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-900">{t.description || 'Izohsiz'}</p>
                    <p className="text-xs text-slate-500">{formatDate(t.date)}</p>
                  </div>
                  <div className={`text-sm font-medium ${t.type === 'income' ? 'text-emerald-600' : 'text-slate-900'}`}>
                    {t.type === 'income' ? '+' : '-'}{formatUZS(t.amount)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </PageTransition>
  );
}
