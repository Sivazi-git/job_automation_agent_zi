# Frontend Rules

## Language & Framework
- TypeScript strict mode; no `any` unless unavoidable (add comment explaining why)
- Next.js 14 App Router — use `'use client'` only when component needs browser APIs or hooks
- 2-space indentation; single quotes for strings

## Styling
- Pure Tailwind CSS — no inline styles, no CSS modules, no shadcn/ui
- Dark theme palette: `slate-950` page bg, `slate-900` card bg, `slate-800` input/hover, `indigo-600` primary accent
- Interactive states: always include `hover:`, `focus:`, `disabled:` variants
- Use `cn()` from `lib/utils.ts` for conditional class merging

## API Calls
- All fetch calls go through `apiFetch` in `lib/api.ts` — never call `fetch()` directly in components
- `apiFetch` automatically injects Bearer token and handles 401 redirect
- New endpoints: add typed function to `lib/api.ts`; export interface for response shape
- Auth functions (`login`, `register`, `getMe`, etc.) are separate from `apiFetch` for public endpoints

## Auth
- Token helpers: `getToken()`, `setToken()`, `clearToken()`, `isAuthenticated()` from `lib/auth.ts`
- After login/register: call `setToken(res.access_token)` then `setUser(res.user)` then `router.push()`
- `useAuth()` hook from `AuthProvider.tsx` gives `{ user, setUser, logout, loading }`
- Protected pages are handled by `AppShell.tsx` — no need for per-page auth checks

## Component Patterns
- Loading state: centered spinner `animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500`
- Error state: `rounded-xl bg-red-900/20 border border-red-800/50 p-4 text-red-400 text-sm`
- Cards: `bg-slate-800 border border-slate-700 rounded-xl p-6`
- Buttons (primary): `bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium rounded-lg px-4 py-2.5 transition-colors`
- Buttons (secondary): `border border-slate-700 hover:bg-slate-800 text-slate-300 text-sm font-medium rounded-lg`

## State Management
- Local `useState` + `useCallback` for page-level state; no global state library needed
- Data fetching: fetch in `useEffect` with a `load` callback wrapped in `useCallback`
- Always handle loading, error, and empty states

## File Naming
- Pages: `app/<route>/page.tsx`
- Components: `components/PascalCase.tsx`
- Utilities: `lib/camelCase.ts`
