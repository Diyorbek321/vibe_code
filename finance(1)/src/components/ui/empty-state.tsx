import { LucideIcon } from 'lucide-react';
import { ReactNode } from 'react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ icon: Icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-8 text-center border-2 border-dashed border-slate-200 rounded-xl bg-slate-50/50">
      <div className="flex items-center justify-center w-12 h-12 mb-4 rounded-full bg-indigo-100">
        <Icon className="w-6 h-6 text-indigo-600" />
      </div>
      <h3 className="mb-1 text-sm font-semibold text-slate-900">{title}</h3>
      <p className="mb-4 text-sm text-slate-500 max-w-sm">{description}</p>
      {action}
    </div>
  );
}
