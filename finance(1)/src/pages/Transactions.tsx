import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Button } from '../components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { Search, Trash2, Receipt, Plus, Download, FileText, FileSpreadsheet } from 'lucide-react';
import { useTransactions, useDeleteTransaction, useCategories } from '../hooks/useTransactions';
import { formatUZS, formatDate } from '../lib/formatters';
import { toast } from 'sonner';
import { PageTransition } from '../components/layout/PageTransition';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { startOfMonth, endOfMonth, subMonths, startOfYear, endOfYear, isWithinInterval } from 'date-fns';
import { EmptyState } from '../components/ui/empty-state';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { TransactionForm } from '../components/forms/TransactionForm';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '../components/ui/dropdown-menu';
import { tokenStorage } from '../lib/api';

export function Transactions() {
  const { data: transactions = [], isLoading } = useTransactions();
  const { data: categories = [] } = useCategories();
  const deleteMutation = useDeleteTransaction();
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'income' | 'expense'>('all');
  const [dateFilter, setDateFilter] = useState('thisMonth');
  const [categoryFilter, setCategoryFilter] = useState('all');

  const now = new Date();

  const filteredTransactions = transactions.filter(t => {
    const matchesSearch = t.description?.toLowerCase().includes(search.toLowerCase());
    const matchesType = filterType === 'all' || t.type === filterType;
    const matchesCategory = categoryFilter === 'all' || t.categoryId === categoryFilter;
    
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

    return matchesSearch && matchesType && matchesCategory && dateMatch;
  });

  const handleDelete = async (id: string) => {
    try {
      await deleteMutation.mutateAsync(id);
      toast.success('O\'chirildi');
    } catch (error) {
      toast.error('Xatolik yuz berdi');
    }
  };

  const getCategoryName = (id: string) => categories.find(c => c.id === id)?.name || 'Noma\'lum';

  const handleExport = async (format: 'csv' | 'excel') => {
    setIsExporting(true);
    try {
      const params = new URLSearchParams();
      if (filterType !== 'all') params.set('type', filterType);

      const now = new Date();
      if (dateFilter === 'thisMonth') {
        params.set('date_from', startOfMonth(now).toISOString());
        params.set('date_to', endOfMonth(now).toISOString());
      } else if (dateFilter === 'lastMonth') {
        const last = subMonths(now, 1);
        params.set('date_from', startOfMonth(last).toISOString());
        params.set('date_to', endOfMonth(last).toISOString());
      } else if (dateFilter === 'thisYear') {
        params.set('date_from', startOfYear(now).toISOString());
        params.set('date_to', endOfYear(now).toISOString());
      }

      const endpoint = format === 'csv' ? '/api/transactions/export/csv' : '/api/transactions/export/excel';
      const url = `${endpoint}?${params.toString()}`;

      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${tokenStorage.get()}` },
      });

      if (!res.ok) {
        toast.error('Eksport amalga oshmadi');
        return;
      }

      const blob = await res.blob();
      const ext = format === 'csv' ? 'csv' : 'xlsx';
      const filename = `tranzaksiyalar_${new Date().toISOString().slice(0, 10)}.${ext}`;
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = filename;
      link.click();
      URL.revokeObjectURL(link.href);
      toast.success(`${format.toUpperCase()} yuklab olindi`);
    } catch {
      toast.error('Eksport xatosi');
    } finally {
      setIsExporting(false);
    }
  };

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Yuklanmoqda...</div>;
  }

  return (
    <PageTransition className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <h1 className="text-2xl font-bold text-slate-900">Tranzaksiyalar</h1>
        
        <div className="flex gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" disabled={isExporting}>
                <Download className="w-4 h-4 mr-2" />
                {isExporting ? 'Yuklanmoqda...' : 'Eksport'}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleExport('csv')}>
                <FileText className="w-4 h-4 mr-2 text-emerald-600" />
                CSV yuklab olish
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleExport('excel')}>
                <FileSpreadsheet className="w-4 h-4 mr-2 text-emerald-600" />
                Excel yuklab olish
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

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
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col gap-4">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-slate-400" />
                <Input
                  placeholder="Izlash..."
                  className="pl-9"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="flex gap-2">
                <Button 
                  variant={filterType === 'all' ? 'default' : 'outline'}
                  onClick={() => setFilterType('all')}
                >
                  Barchasi
                </Button>
                <Button 
                  variant={filterType === 'income' ? 'default' : 'outline'}
                  onClick={() => setFilterType('income')}
                  className={filterType === 'income' ? 'bg-emerald-600 hover:bg-emerald-700' : ''}
                >
                  Daromad
                </Button>
                <Button 
                  variant={filterType === 'expense' ? 'default' : 'outline'}
                  onClick={() => setFilterType('expense')}
                  className={filterType === 'expense' ? 'bg-rose-600 hover:bg-rose-700' : ''}
                >
                  Xarajat
                </Button>
              </div>
            </div>
            
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="flex-1">
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
              <div className="flex-1">
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
          </div>
        </CardHeader>
        <CardContent>
          {filteredTransactions.length === 0 ? (
            <EmptyState 
              icon={Receipt}
              title="Tranzaksiyalar topilmadi"
              description="Siz qidirayotgan yoki filtrlarga mos keladigan tranzaksiya yo'q."
              action={
                <Button onClick={() => setIsAddOpen(true)} variant="outline" className="mt-2">
                  <Plus className="w-4 h-4 mr-2" />
                  Yangi qo'shish
                </Button>
              }
            />
          ) : (
            <div className="rounded-md border border-slate-200">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Sana</TableHead>
                    <TableHead>Kategoriya</TableHead>
                    <TableHead>Izoh</TableHead>
                    <TableHead className="text-right">Summa</TableHead>
                    <TableHead className="w-[50px]"></TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredTransactions.map((t) => (
                    <TableRow key={t.id}>
                      <TableCell className="whitespace-nowrap">{formatDate(t.date)}</TableCell>
                      <TableCell>
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-800">
                          {getCategoryName(t.categoryId)}
                        </span>
                      </TableCell>
                      <TableCell>{t.description || '-'}</TableCell>
                      <TableCell className={`text-right font-medium ${t.type === 'income' ? 'text-emerald-600' : 'text-slate-900'}`}>
                        {t.type === 'income' ? '+' : '-'}{formatUZS(t.amount)}
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" onClick={() => handleDelete(t.id)}>
                          <Trash2 className="w-4 h-4 text-slate-400 hover:text-rose-500" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </PageTransition>
  );
}
