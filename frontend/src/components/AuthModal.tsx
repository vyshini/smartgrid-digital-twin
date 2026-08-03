import React, { useState } from 'react';
import { User } from '../types/index.js';
import { api } from '../api/client.js';
import { ShieldCheck, Lock, User as UserIcon, X, CheckCircle } from 'lucide-react';

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUserUpdate: (user: User) => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onUserUpdate }) => {
  const [username, setUsername] = useState<string>('admin');
  const [password, setPassword] = useState<string>('change-me-immediately');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const res = await api.login(username, password);
      onUserUpdate(res.user);
      onClose();
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="w-full max-w-md p-6 rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 p-1 rounded-lg text-slate-400 hover:text-white bg-slate-800"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-2 text-cyan-400 mb-2">
          <ShieldCheck className="h-6 w-6" />
          <h2 className="text-xl font-extrabold text-white">SmartGrid Operator Auth</h2>
        </div>
        <p className="text-xs text-slate-400 mb-6">
          Authenticate as a Grid Operator or System Administrator to trigger QAOA optimization runs and scenario stress tests.
        </p>

        {error && (
          <div className="p-3 mb-4 rounded-xl bg-red-500/10 border border-red-500/30 text-xs text-red-300">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4 text-xs font-semibold">
          <div>
            <label className="block text-slate-300 mb-1">Username / Operator ID</label>
            <div className="relative">
              <UserIcon className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500"
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-slate-300 mb-1">Password</label>
            <div className="relative">
              <Lock className="h-4 w-4 text-slate-500 absolute left-3 top-3" />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-9 pr-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-white focus:outline-none focus:border-cyan-500"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-extrabold shadow-lg shadow-cyan-500/20 transition mt-2 flex items-center justify-center gap-2"
          >
            {loading ? 'Authenticating...' : 'Sign In as Grid Operator'}
          </button>
        </form>

        <div className="mt-4 pt-4 border-t border-slate-800/80 text-[11px] text-slate-400 space-y-1">
          <p className="font-bold text-slate-300">Default Demo Credentials:</p>
          <p>• Admin: <code className="text-cyan-300 font-mono">admin</code> / <code className="text-cyan-300 font-mono">change-me-immediately</code></p>
          <p>• Operator: <code className="text-cyan-300 font-mono">operator</code> / <code className="text-cyan-300 font-mono">operator123</code></p>
        </div>
      </div>
    </div>
  );
};
