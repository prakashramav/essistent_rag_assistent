"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { api, clearAuthStorage, getAccessToken, setActiveOrgId, setTokens } from "@/lib/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [activeOrg, setActiveOrg] = useState(null);
  const [organizations, setOrganizations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchCurrentUser = async () => {
    try {
      setLoading(true);
      const data = await api.auth.me();
      setUser({
        id: data.id,
        email: data.email,
        fullName: data.full_name,
        isActive: data.is_active,
      });
      setActiveOrg(data.active_organization);
      setOrganizations(data.organizations || []);
      if (data.active_organization) {
        setActiveOrgId(data.active_organization.id);
      }
      setError(null);
    } catch (err) {
      console.warn("Failed to fetch authenticated user session:", err.message);
      clearAuthStorage();
      setUser(null);
      setActiveOrg(null);
      setOrganizations([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const token = getAccessToken();
    if (token) {
      fetchCurrentUser();
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email, password) => {
    setError(null);
    try {
      const data = await api.auth.login({ email, password });
      setTokens(data.access_token, data.refresh_token);
      if (data.organization) {
        setActiveOrgId(data.organization.id);
        setActiveOrg(data.organization);
      }
      setUser({
        id: data.user.id,
        email: data.user.email,
        fullName: data.user.full_name,
        isActive: data.user.is_active,
      });
      setOrganizations(data.user.organizations || []);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const signup = async ({ fullName, email, password, organizationName }) => {
    setError(null);
    try {
      const data = await api.auth.signup({
        full_name: fullName,
        email,
        password,
        organization_name: organizationName,
      });
      setTokens(data.access_token, data.refresh_token);
      if (data.organization) {
        setActiveOrgId(data.organization.id);
        setActiveOrg(data.organization);
      }
      setUser({
        id: data.user.id,
        email: data.user.email,
        fullName: data.user.full_name,
        isActive: data.user.is_active,
      });
      setOrganizations(data.user.organizations || []);
      return data;
    } catch (err) {
      setError(err.message);
      throw err;
    }
  };

  const switchOrg = (orgId) => {
    const org = organizations.find((o) => o.id === orgId);
    if (org) {
      setActiveOrgId(org.id);
      setActiveOrg(org);
      window.location.reload();
    }
  };

  const logout = () => {
    clearAuthStorage();
    setUser(null);
    setActiveOrg(null);
    setOrganizations([]);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        activeOrg,
        organizations,
        loading,
        error,
        login,
        signup,
        switchOrg,
        logout,
        refreshUser: fetchCurrentUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
