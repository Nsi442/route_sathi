import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { authApi } from '../api/endpoints';
import { getToken, setToken, setUnauthorizedHandler } from '../api/client';

const AuthContext = createContext(null);

/** Landing route for each role after a successful sign-in. */
export const HOME_FOR_ROLE = {
  USER: '/home',
  AUTHORITY: '/authority',
  MAINTENANCE: '/maintenance',
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setToken(null);
      setUser(null);
    });
  }, []);

  // Restore the session on a page refresh.
  useEffect(() => {
    let cancelled = false;
    async function restore() {
      if (!getToken()) {
        setLoading(false);
        return;
      }
      try {
        const profile = await authApi.me();
        if (!cancelled) setUser(profile);
      } catch {
        setToken(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    restore();
    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email, password, role) => {
    const data = await authApi.login({ email, password, role: role || null });
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  }, []);

  const signUp = useCallback(async (payload) => {
    const data = await authApi.signup(payload);
    setToken(data.access_token);
    setUser(data.user);
    return data.user;
  }, []);

  const value = useMemo(
    () => ({
      user,
      loading,
      signIn,
      signUp,
      signOut,
      setUser,
      isAuthenticated: Boolean(user),
      role: user?.role || null,
    }),
    [user, loading, signIn, signUp, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider');
  return context;
}
