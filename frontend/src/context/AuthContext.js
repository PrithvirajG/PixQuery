import React, { createContext, useState, useEffect, useContext } from 'react';
import axios from 'axios';
import { API_BASE as API } from '../lib/apiBase';
import { setEventToken } from '../lib/eventSocket';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(localStorage.getItem('pixquery_token') || null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Keep the live-event socket authenticated with the same token as the REST
  // calls, so logging in connects it and logging out tears it down.
  useEffect(() => {
    setEventToken(token);
  }, [token]);

  // Set default authorization header and request interceptor for axios
  useEffect(() => {
    const interceptor = axios.interceptors.request.use(
      (config) => {
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Fetch user profile if token is present
    if (token) {
      axios.get(`${API}/auth/me`)
        .then(res => {
          setUser(res.data);
          setLoading(false);
        })
        .catch(err => {
          console.error("Session verification failed", err);
          // Session expired or invalid, clear token
          logout();
          setLoading(false);
        });
    } else {
      setLoading(false);
    }

    return () => {
      axios.interceptors.request.eject(interceptor);
    };
  }, [token]);

  const login = async (username, password) => {
    try {
      const res = await axios.post(`${API}/auth/login`, { username, password });
      const { access_token } = res.data;
      localStorage.setItem('pixquery_token', access_token);
      setToken(access_token);
      return true;
    } catch (err) {
      console.error("Login request failed", err);
      throw err;
    }
  };

  const register = async (username, password) => {
    try {
      await axios.post(`${API}/auth/register`, { username, password });
      // Immediately log in after successful registration
      return await login(username, password);
    } catch (err) {
      console.error("Registration request failed", err);
      throw err;
    }
  };

  const logout = () => {
    localStorage.removeItem('pixquery_token');
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ token, user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
