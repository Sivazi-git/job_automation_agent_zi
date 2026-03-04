'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import { useAuth } from '@/components/AuthProvider';
import { isAuthenticated } from '@/lib/auth';

const PUBLIC_PATHS = ['/login', '/signup'];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { loading } = useAuth();

  const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

  useEffect(() => {
    if (loading) return;
    if (!isPublic && !isAuthenticated()) {
      router.replace('/login');
    }
  }, [loading, isPublic, router, pathname]);

  // Public pages — no sidebar
  if (isPublic) {
    return <>{children}</>;
  }

  // Show nothing while checking auth
  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500" />
      </div>
    );
  }

  // Authenticated layout
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
