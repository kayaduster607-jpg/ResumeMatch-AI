import axios from "axios";

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  timeout: 180000,
  headers: { "Content-Type": "application/json" },
});

client.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const message =
      err.response?.data?.message || err.message || "请求失败";
    return Promise.reject(new Error(message));
  }
);

export default client;
