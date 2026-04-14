import { Link, Outlet, useLocation } from 'react-router-dom';
import { LayoutDashboard, Receipt, PieChart, Tags, LogOut, Menu } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { cn } from '../../lib/utils';
import { useState } from 'react';
import { Button } from '../ui/button';

const navigation = [
  { name: 'Umumiy', href: '/overview', icon: LayoutDashboard },
  { name: 'Tranzaksiyalar', href: '/transactions', icon: Receipt },
  { name: 'Analitika', href: '/analytics', icon: PieChart },
  { name: 'Kategoriyalar', href: '/categories-budgets', icon: Tags },
];

export function AppLayout() {
  const location = useLocation();
  const logout = useAuthStore((state) => state.logout);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen bg-slate-50">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-slate-900/80 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={cn(
        "fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-200 transform transition-transform duration-200 ease-in-out lg:translate-x-0 lg:static lg:block",
        sidebarOpen ? "translate-x-0" : "-translate-x-full"
      )}>
        <div className="flex flex-col h-full">
          <div className="flex items-center h-16 px-6 border-b border-slate-200">
            <div className="flex items-center gap-2 font-bold text-xl text-indigo-600">
              <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
                <span className="text-white text-lg">M</span>
              </div>
              Moliya
            </div>
          </div>

          <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
            {navigation.map((item) => {
              const isActive = location.pathname.startsWith(item.href);
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                    isActive 
                      ? "bg-indigo-50 text-indigo-700" 
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                  )}
                >
                  <item.icon className={cn("w-5 h-5", isActive ? "text-indigo-700" : "text-slate-400")} />
                  {item.name}
                </Link>
              );
            })}
          </nav>

          <div className="p-4 border-t border-slate-200">
            <button
              onClick={logout}
              className="flex items-center gap-3 px-3 py-2.5 w-full rounded-lg text-sm font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition-colors"
            >
              <LogOut className="w-5 h-5 text-slate-400" />
              Chiqish
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <header className="flex items-center h-16 px-4 sm:px-6 lg:px-8 bg-white border-b border-slate-200 lg:hidden">
          <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(true)} className="-ml-2">
            <Menu className="w-6 h-6" />
          </Button>
          <div className="ml-4 font-bold text-lg text-slate-900">Moliya</div>
        </header>

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
