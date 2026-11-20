import { createContext, useContext, useState, useEffect } from 'react';
import { authAPI } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('user');
    return saved ? JSON.parse(saved) : null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      authAPI.me().then(res => {
        setUser(res.data);
        localStorage.setItem('user', JSON.stringify(res.data));
        setLoading(false);
      }).catch(() => {
        logout();
        setLoading(false);
      });
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (username, password) => {
    const res = await authAPI.login(username, password);
    localStorage.setItem('access_token', res.data.access);
    localStorage.setItem('refresh_token', res.data.refresh);
    localStorage.setItem('user', JSON.stringify(res.data.user));
    setUser(res.data.user);
    return res.data.user;
  };

  const logout = () => {
    // E15: revoke the refresh token server-side (fire and forget).
    const refresh = localStorage.getItem('refresh_token');
    if (refresh) authAPI.logout(refresh).catch(() => {});
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');
    setUser(null);
  };

  // Replace the signed-in user's details (e.g. after changing password).
  const updateUser = (u) => {
    localStorage.setItem('user', JSON.stringify(u));
    setUser(u);
  };

  const isAdmin = user?.role === 'admin';
  const isPlant = user?.role === 'plant';
  // Day-to-day data (entries, sales, medicines, feed, bills): any supervisor, any farm —
  // they cover for each other. Regions only set the default scope of dashboards/reports.
  const canEditFarm = () => isAdmin || user?.role === 'supervisor';
  // A farm's own details (owner, capacity, region) and deleting it: admin, or its region's supervisor.
  const canManageFarm = (farmId) => isAdmin || !!user?.assigned_farm_ids?.includes(farmId);

  return (
    <AuthContext.Provider value={{ user, login, logout, updateUser, loading, isAdmin, isPlant, canEditFarm, canManageFarm }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
