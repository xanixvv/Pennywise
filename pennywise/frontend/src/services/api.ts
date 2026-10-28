const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';
export async function request<T=any>(path:string, options:RequestInit={}) : Promise<T> {
  const response = await fetch(`${API}${path}`, { ...options, headers:{ ...(options.body ? {'Content-Type':'application/json'} : {}), ...options.headers } });
  if (!response.ok) { let message = `Request failed (${response.status})`; try { const body=await response.json(); message=body.detail || message; } catch {} throw new Error(message); }
  return response.json();
}
export const json = (method:string, body:unknown):RequestInit => ({method, body:JSON.stringify(body)});
export { API };
