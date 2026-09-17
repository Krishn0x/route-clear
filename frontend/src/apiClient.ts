import axios from 'axios';

// Use the VITE_API_URL environment variable if set (for production),
// otherwise default to empty string (which uses relative paths for the Vite proxy)
const baseURL = (import.meta as any).env.VITE_API_URL || "";

export const apiClient = axios.create({
  baseURL,
});

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("demo_token");
  if (token) {
    config.headers["x-demo-token"] = token;
  }
  return config;
});
