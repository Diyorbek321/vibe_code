import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { useCategories, useTransactions } from '../hooks/useTransactions';
import { formatUZS } from '../lib/formatters';
import { Progress } from '../components/ui/progress';
import { PageTransition } from '../components/layout/PageTransition';
import { EmptyState } from '../components/ui/empty-state';
import { Tags } from 'lucide-react';

export function Categories() {
  const { data: categories = [], isLoading: catLoading } = useCategories();
  const { data: transactions = [], isLoading: txLoading } = useTransactions();

  if (catLoading || txLoading) {
    return <div className="p-8 text-center text-slate-500">Yuklanmoqda...</div>;
  }

  const expenses = categories.filter(c => c.type === 'expense');
  const incomes = categories.filter(c => c.type === 'income');

  const getCategorySpent = (categoryId: string) => {
    return transactions
      .filter(t => t.categoryId === categoryId)
      .reduce((sum, t) => sum + t.amount, 0);
  };

  if (categories.length === 0) {
    return (
      <PageTransition className="space-y-6">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <h1 className="text-2xl font-bold text-slate-900">Kategoriyalar va byudjet</h1>
        </div>
        <EmptyState 
          icon={Tags}
          title="Kategoriyalar yo'q"
          description="Hozircha hech qanday kategoriya qo'shilmagan. Tranzaksiyalarni toifalash uchun kategoriya yarating."
        />
      </PageTransition>
    );
  }

  return (
    <PageTransition className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-2xl font-bold text-slate-900">Kategoriyalar va byudjet</h1>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="space-y-6">
          <h2 className="text-lg font-semibold text-slate-900">Xarajatlar</h2>
          {expenses.length === 0 ? (
            <p className="text-sm text-slate-500">Xarajat kategoriyalari yo'q</p>
          ) : (
            expenses.map(category => {
              const spent = getCategorySpent(category.id);
              const limit = category.budgetLimit || 0;
              const percent = limit > 0 ? Math.min(100, (spent / limit) * 100) : 0;
              const isOverBudget = spent > limit && limit > 0;

              return (
                <Card key={category.id}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <div 
                          className="w-3 h-3 rounded-full" 
                          style={{ backgroundColor: category.color }} 
                        />
                        <span className="font-medium text-slate-900">{category.name}</span>
                      </div>
                      <span className="text-sm font-medium text-slate-900">
                        {formatUZS(spent)}
                      </span>
                    </div>
                    
                    {limit > 0 && (
                      <>
                        <Progress 
                          value={percent} 
                          className={`h-2 mt-3 ${isOverBudget ? 'bg-rose-100' : ''}`}
                          indicatorClassName={isOverBudget ? 'bg-rose-500' : 'bg-indigo-600'}
                        />
                        <div className="flex justify-between mt-2 text-xs text-slate-500">
                          <span>{percent.toFixed(1)}% ishlatildi</span>
                          <span>Limit: {formatUZS(limit)}</span>
                        </div>
                      </>
                    )}
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>

        <div className="space-y-6">
          <h2 className="text-lg font-semibold text-slate-900">Daromadlar</h2>
          {incomes.length === 0 ? (
            <p className="text-sm text-slate-500">Daromad kategoriyalari yo'q</p>
          ) : (
            incomes.map(category => {
              const earned = getCategorySpent(category.id);

              return (
                <Card key={category.id}>
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div 
                          className="w-3 h-3 rounded-full" 
                          style={{ backgroundColor: category.color }} 
                        />
                        <span className="font-medium text-slate-900">{category.name}</span>
                      </div>
                      <span className="text-sm font-medium text-emerald-600">
                        +{formatUZS(earned)}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              );
            })
          )}
        </div>
      </div>
    </PageTransition>
  );
}
