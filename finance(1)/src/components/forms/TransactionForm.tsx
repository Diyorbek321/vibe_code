import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { useAddTransaction, useCategories } from '../../hooks/useTransactions';
import { toast } from 'sonner';

const schema = z.object({
  amount: z.number().min(1, 'Summani kiriting'),
  type: z.enum(['income', 'expense']),
  categoryId: z.string().min(1, 'Kategoriyani tanlang'),
  date: z.string().min(1, 'Sanani kiriting'),
  description: z.string().optional(),
});

type FormData = z.infer<typeof schema>;

export function TransactionForm({ onSuccess }: { onSuccess: () => void }) {
  const { data: categories = [] } = useCategories();
  const addMutation = useAddTransaction();

  const { register, handleSubmit, setValue, watch, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: {
      type: 'expense',
      date: new Date().toISOString().split('T')[0],
    }
  });

  const type = watch('type');
  const filteredCategories = categories.filter(c => c.type === type);

  const onSubmit = async (data: FormData) => {
    try {
      await addMutation.mutateAsync({
        ...data,
        date: new Date(data.date).toISOString(),
      });
      toast.success('Tranzaksiya muvaffaqiyatli qo\'shildi');
      onSuccess();
    } catch (error) {
      toast.error('Xatolik yuz berdi');
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="space-y-2">
        <Label>Tur</Label>
        <Select onValueChange={(v: 'income' | 'expense') => setValue('type', v)} value={type}>
          <SelectTrigger>
            <SelectValue placeholder="Turni tanlang" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="expense">Xarajat</SelectItem>
            <SelectItem value="income">Daromad</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label>Summa (UZS)</Label>
        <Input 
          type="number" 
          {...register('amount', { valueAsNumber: true })} 
          placeholder="0"
        />
        {errors.amount && <p className="text-sm text-red-500">{errors.amount.message}</p>}
      </div>

      <div className="space-y-2">
        <Label>Kategoriya</Label>
        <Select onValueChange={(v: string) => setValue('categoryId', v)} value={watch('categoryId')}>
          <SelectTrigger>
            <SelectValue placeholder="Kategoriyani tanlang" />
          </SelectTrigger>
          <SelectContent>
            {filteredCategories.map(c => (
              <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {errors.categoryId && <p className="text-sm text-red-500">{errors.categoryId.message}</p>}
      </div>

      <div className="space-y-2">
        <Label>Sana</Label>
        <Input type="date" {...register('date')} />
        {errors.date && <p className="text-sm text-red-500">{errors.date.message}</p>}
      </div>

      <div className="space-y-2">
        <Label>Izoh (ixtiyoriy)</Label>
        <Input {...register('description')} placeholder="Nima uchun?" />
      </div>

      <div className="pt-4 flex justify-end space-x-2">
        <Button type="submit" disabled={addMutation.isPending} className="w-full bg-indigo-600 hover:bg-indigo-700">
          {addMutation.isPending ? 'Saqlanmoqda...' : 'Saqlash'}
        </Button>
      </div>
    </form>
  );
}
