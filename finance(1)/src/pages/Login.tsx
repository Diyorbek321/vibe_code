import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Wallet } from 'lucide-react';
import { toast } from 'sonner';
import { ApiError } from '../lib/api';

import { PageTransition } from '../components/layout/PageTransition';

type Tab = 'login' | 'register';

export function Login() {
  const navigate = useNavigate();
  const loginWithApi = useAuthStore((state) => state.loginWithApi);
  const registerWithApi = useAuthStore((state) => state.registerWithApi);

  const [tab, setTab] = useState<Tab>('login');
  const [loading, setLoading] = useState(false);

  // Login fields
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // Register fields
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirm, setRegConfirm] = useState('');
  const [regFullName, setRegFullName] = useState('');
  const [regCompany, setRegCompany] = useState('');

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) {
      toast.error('Email va parolni kiriting');
      return;
    }
    setLoading(true);
    try {
      await loginWithApi(email, password);
      toast.success('Tizimga kirdingiz');
      navigate('/overview');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Email yoki parol noto\'g\'ri';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regEmail || !regPassword || !regFullName || !regCompany) {
      toast.error('Barcha maydonlarni to\'ldiring');
      return;
    }
    if (regPassword.length < 8) {
      toast.error('Parol kamida 8 ta belgi bo\'lishi kerak');
      return;
    }
    if (regPassword !== regConfirm) {
      toast.error('Parollar mos kelmadi');
      return;
    }
    setLoading(true);
    try {
      await registerWithApi(regEmail, regPassword, regFullName, regCompany);
      toast.success('Ro\'yxatdan o\'tdingiz! Xush kelibsiz!');
      navigate('/overview');
    } catch (err) {
      const msg = err instanceof ApiError ? err.detail : 'Ro\'yxatdan o\'tishda xatolik';
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <PageTransition className="min-h-screen bg-slate-50 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      <div className="sm:mx-auto sm:w-full sm:max-w-md">
        <div className="flex justify-center">
          <div className="w-12 h-12 bg-indigo-600 rounded-xl flex items-center justify-center">
            <Wallet className="w-6 h-6 text-white" />
          </div>
        </div>
        <h2 className="mt-6 text-center text-3xl font-extrabold text-slate-900">
          {tab === 'login' ? 'Tizimga kirish' : 'Ro\'yxatdan o\'tish'}
        </h2>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        {/* Tabs */}
        <div className="flex rounded-lg bg-slate-200 p-1 mb-4">
          <button
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
              tab === 'login'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
            onClick={() => setTab('login')}
          >
            Kirish
          </button>
          <button
            className={`flex-1 py-2 text-sm font-medium rounded-md transition-colors ${
              tab === 'register'
                ? 'bg-white text-slate-900 shadow-sm'
                : 'text-slate-600 hover:text-slate-900'
            }`}
            onClick={() => setTab('register')}
          >
            Ro'yxatdan o'tish
          </button>
        </div>

        <Card>
          {tab === 'login' ? (
            <>
              <CardHeader>
                <CardTitle>Xush kelibsiz</CardTitle>
                <CardDescription>
                  Moliya boshqaruvi tizimiga kirish uchun ma'lumotlaringizni kiriting
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleLogin} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="email">Email manzil</Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="admin@example.uz"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="password">Parol</Label>
                    <Input
                      id="password"
                      type="password"
                      placeholder="••••••••"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                  <Button
                    type="submit"
                    className="w-full bg-indigo-600 hover:bg-indigo-700"
                    disabled={loading}
                  >
                    {loading ? 'Kirilmoqda...' : 'Kirish'}
                  </Button>
                  <p className="text-center text-sm text-slate-500">
                    Hisobingiz yo'qmi?{' '}
                    <button
                      type="button"
                      className="text-indigo-600 hover:underline font-medium"
                      onClick={() => setTab('register')}
                    >
                      Ro'yxatdan o'ting
                    </button>
                  </p>
                </form>
              </CardContent>
            </>
          ) : (
            <>
              <CardHeader>
                <CardTitle>Yangi hisob yaratish</CardTitle>
                <CardDescription>
                  Kompaniyangizni ro'yxatdan o'tiring va moliya boshqaruvini boshlang
                </CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleRegister} className="space-y-4">
                  <div className="space-y-2">
                    <Label htmlFor="reg-fullname">Ism Familiya</Label>
                    <Input
                      id="reg-fullname"
                      type="text"
                      placeholder="Jasur Toshmatov"
                      value={regFullName}
                      onChange={(e) => setRegFullName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="reg-company">Kompaniya nomi</Label>
                    <Input
                      id="reg-company"
                      type="text"
                      placeholder="Toshmatov Savdo"
                      value={regCompany}
                      onChange={(e) => setRegCompany(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="reg-email">Email manzil</Label>
                    <Input
                      id="reg-email"
                      type="email"
                      placeholder="jasur@toshmatov.uz"
                      value={regEmail}
                      onChange={(e) => setRegEmail(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="reg-password">Parol</Label>
                    <Input
                      id="reg-password"
                      type="password"
                      placeholder="Kamida 8 ta belgi"
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="reg-confirm">Parolni tasdiqlang</Label>
                    <Input
                      id="reg-confirm"
                      type="password"
                      placeholder="••••••••"
                      value={regConfirm}
                      onChange={(e) => setRegConfirm(e.target.value)}
                    />
                  </div>
                  <Button
                    type="submit"
                    className="w-full bg-indigo-600 hover:bg-indigo-700"
                    disabled={loading}
                  >
                    {loading ? 'Ro\'yxatdan o\'tilmoqda...' : 'Ro\'yxatdan o\'tish'}
                  </Button>
                  <p className="text-center text-sm text-slate-500">
                    Hisobingiz bormi?{' '}
                    <button
                      type="button"
                      className="text-indigo-600 hover:underline font-medium"
                      onClick={() => setTab('login')}
                    >
                      Kirish
                    </button>
                  </p>
                </form>
              </CardContent>
            </>
          )}
        </Card>
      </div>
    </PageTransition>
  );
}
