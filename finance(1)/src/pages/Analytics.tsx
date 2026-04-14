import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { useTransactions, useCategories } from '../hooks/useTransactions';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts';
import { formatUZS } from '../lib/formatters';
import { PageTransition } from '../components/layout/PageTransition';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { startOfMonth, endOfMonth, subMonths, startOfYear, endOfYear, isWithinInterval } from 'date-fns';
import { EmptyState } from '../components/ui/empty-state';
import { BarChart3, Plus } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { TransactionForm } from '../components/forms/TransactionForm';
import { Button } from '../components/ui/button';

export function Analytics() {
  const { data: transactions = [], isLoading } = useTransactions();
  const { data: categories = [] } = useCategories();
  const [isAddOpen, setIsAddOpen] = useState(false);

  const [dateFilter, setDateFilter] = useState('thisMonth');
  const [typeFilter, setTypeFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState('all');

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Yuklanmoqda...</div>;
  }

  const now = new Date();
  
  const filteredTransactions = transactions.filter(t => {
    const date = new Date(t.date);
    let dateMatch = true;
    
    if (dateFilter === 'thisMonth') {
      dateMatch = isWithinInterval(date, { start: startOfMonth(now), end: endOfMonth(now) });
    } else if (dateFilter === 'lastMonth') {
      const lastMonth = subMonths(now, 1);
      dateMatch = isWithinInterval(date, { start: startOfMonth(lastMonth), end: endOfMonth(lastMonth) });
    } else if (dateFilter === 'thisYear') {
      dateMatch = isWithinInterval(date, { start: startOfYear(now), end: endOfYear(now) });
    }

    const typeMatch = typeFilter === 'all' || t.type === typeFilter;
    const categoryMatch = categoryFilter === 'all' || t.categoryId === categoryFilter;

    return dateMatch && typeMatch && categoryMatch;
  });

  // Process data for bar chart (trend over time)
  const trendData = filteredTransactions.reduce((acc, t) => {
    const date = new Date(t.date);
    // Group by day if this month/last month, otherwise group by month
    const key = (dateFilter === 'thisMonth' || dateFilter === 'lastMonth') 
      ? `${date.getDate()}-${String(date.getMonth() + 1).padStart(2, '0')}`
      : `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
    
    if (!acc[key]) {
      acc[key] = { name: key, income: 0, expense: 0 };
    }
    
    if (t.type === 'income') acc[key].income += t.amount;
    else acc[key].expense += t.amount;
    
    return acc;
  }, {} as Record<string, any>);

  const barData = Object.values(trendData).sort((a, b) => a.name.localeCompare(b.name));

  // Process data for pie chart (expenses by category)
  const expensesByCategory = filteredTransactions
    .filter(t => t.type === 'expense')
    .reduce((acc, t) => {
      if (!acc[t.categoryId]) acc[t.categoryId] = 0;
      acc[t.categoryId] += t.amount;
      return acc;
    }, {} as Record<string, number>);

  const expensePieData = Object.entries(expensesByCategory).map(([categoryId, value]) => {
    const category = categories.find(c => c.id === categoryId);
    return { name: category?.name || 'Boshqa', value, color: category?.color || '#cbd5e1' };
  }).sort((a, b) => b.value - a.value);

  // Process data for pie chart (income by category)
  const incomeByCategory = filteredTransactions
    .filter(t => t.type === 'income')
    .reduce((acc, t) => {
      if (!acc[t.categoryId]) acc[t.categoryId] = 0;
      acc[t.categoryId] += t.amount;
      return acc;
    }, {} as Record<string, number>);

  const incomePieData = Object.entries(incomeByCategory).map(([categoryId, value]) => {
    const category = categories.find(c => c.id === categoryId);
    return { name: category?.name || 'Boshqa', value, color: category?.color || '#cbd5e1' };
  }).sort((a, b) => b.value - a.value);

  return (
    <PageTransition className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-2xl font-bold text-slate-900">Analitika</h1>
        
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

      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">Davr</label>
              <Select value={dateFilter} onValueChange={setDateFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Davrni tanlang" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="thisMonth">Shu oy</SelectItem>
                  <SelectItem value="lastMonth">O'tgan oy</SelectItem>
                  <SelectItem value="thisYear">Shu yil</SelectItem>
                  <SelectItem value="all">Barcha vaqt</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">Tur</label>
              <Select value={typeFilter} onValueChange={setTypeFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Turni tanlang" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Barchasi</SelectItem>
                  <SelectItem value="income">Daromad</SelectItem>
                  <SelectItem value="expense">Xarajat</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-500">Kategoriya</label>
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Kategoriyani tanlang" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Barcha kategoriyalar</SelectItem>
                  {categories.map(c => (
                    <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {filteredTransactions.length === 0 ? (
        <EmptyState 
          icon={BarChart3}
          title="Ma'lumot topilmadi"
          description="Tanlangan filtrlarga mos keladigan tranzaksiyalar yo'q. Filtrlarni o'zgartirib ko'ring yoki yangi tranzaksiya qo'shing."
          action={
            <Button onClick={() => setIsAddOpen(true)} className="mt-2 bg-indigo-600 hover:bg-indigo-700">
              <Plus className="w-4 h-4 mr-2" />
              Yangi qo'shish
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Daromad va xarajatlar dinamikasi</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e2e8f0" />
                    <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#64748b', fontSize: 12 }} />
                    <YAxis 
                      axisLine={false} 
                      tickLine={false} 
                      tick={{ fill: '#64748b', fontSize: 12 }}
                      tickFormatter={(value) => `${value / 1000000}M`}
                    />
                    <Tooltip 
                      formatter={(value: number) => formatUZS(value)}
                      cursor={{ fill: '#f1f5f9' }}
                      contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                    />
                    <Legend iconType="circle" />
                    {(typeFilter === 'all' || typeFilter === 'income') && (
                      <Bar dataKey="income" name="Daromad" fill="#4f46e5" radius={[4, 4, 0, 0]} />
                    )}
                    {(typeFilter === 'all' || typeFilter === 'expense') && (
                      <Bar dataKey="expense" name="Xarajat" fill="#ef4444" radius={[4, 4, 0, 0]} />
                    )}
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {(typeFilter === 'all' || typeFilter === 'expense') && expensePieData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Xarajatlar tarkibi</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={expensePieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={100}
                        paddingAngle={2}
                        dataKey="value"
                      >
                        {expensePieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip 
                        formatter={(value: number) => formatUZS(value)}
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                      />
                      <Legend iconType="circle" layout="vertical" verticalAlign="middle" align="right" />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}

          {(typeFilter === 'all' || typeFilter === 'income') && incomePieData.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Daromadlar manbalari</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-[300px] w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={incomePieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={100}
                        paddingAngle={2}
                        dataKey="value"
                      >
                        {incomePieData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip 
                        formatter={(value: number) => formatUZS(value)}
                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                      />
                      <Legend iconType="circle" layout="vertical" verticalAlign="middle" align="right" />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </PageTransition>
  );
}
