// Minimal Ersatz für jwt-decode, falls nicht installiert
export function jwtDecode(token) {
  if (!token) return {};
  const payload = token.split('.')[1];
  if (!payload) return {};
  try {
    return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
  } catch {
    return {};
  }
}
