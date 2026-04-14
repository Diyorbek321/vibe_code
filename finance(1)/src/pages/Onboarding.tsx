import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Wallet, Bot, ArrowRight, CheckCircle2 } from 'lucide-react';

import { PageTransition } from '../components/layout/PageTransition';

export function Onboarding() {
  const navigate = useNavigate();
  const completeOnboarding = useAuthStore((state) => state.completeOnboarding);
  const [step, setStep] = useState(1);
  const [categoryName, setCategoryName] = useState('');

  const handleComplete = () => {
    completeOnboarding();
    navigate('/overview');
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
          Xush kelibsiz!
        </h2>
        <p className="mt-2 text-center text-sm text-slate-600">
          Moliya tizimini sozlash uchun bir necha qadam qoldi
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between mb-4">
              <div className="flex space-x-2">
                {[1, 2].map((i) => (
                  <div
                    key={i}
                    className={`h-2 w-12 rounded-full ${
                      i <= step ? 'bg-indigo-600' : 'bg-slate-200'
                    }`}
                  />
                ))}
              </div>
              <span className="text-sm font-medium text-slate-500">
                Qadam {step}/2
              </span>
            </div>
            <CardTitle>
              {step === 1 ? 'Birinchi kategoriyani yarating' : 'Telegram botni ulang'}
            </CardTitle>
            <CardDescription>
              {step === 1 
                ? 'Eng ko\'p ishlatiladigan xarajat yoki daromad turini kiriting'
                : 'Tranzaksiyalarni to\'g\'ridan-to\'g\'ri Telegram orqali qo\'shish uchun botimizga ulaning'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {step === 1 ? (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="category">Kategoriya nomi</Label>
                  <Input
                    id="category"
                    placeholder="Masalan: Ofis ijarasi, Oylik maosh..."
                    value={categoryName}
                    onChange={(e) => setCategoryName(e.target.value)}
                  />
                </div>
                <Button 
                  className="w-full" 
                  onClick={() => setStep(2)}
                  disabled={!categoryName.trim()}
                >
                  Keyingisi
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </div>
            ) : (
              <div className="space-y-6">
                <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 flex items-start space-x-4">
                  <Bot className="w-8 h-8 text-indigo-600 flex-shrink-0" />
                  <div>
                    <h4 className="text-sm font-medium text-slate-900">@MoliyaUzBot</h4>
                    <p className="text-sm text-slate-500 mt-1">
                      Botga o'ting va /start tugmasini bosing. Keyin quyidagi kodni yuboring:
                    </p>
                    <code className="mt-2 block bg-white px-3 py-2 rounded border border-slate-200 text-indigo-600 font-mono text-sm">
                      CONNECT-8492
                    </code>
                  </div>
                </div>
                <div className="flex space-x-3">
                  <Button variant="outline" className="flex-1" onClick={() => setStep(1)}>
                    Orqaga
                  </Button>
                  <Button className="flex-1" onClick={handleComplete}>
                    Boshlash
                    <CheckCircle2 className="w-4 h-4 ml-2" />
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </PageTransition>
  );
}
