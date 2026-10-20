// In-memory access-token store (never localStorage — the refresh token is the only persisted
// credential, and it lives in an httpOnly cookie the browser manages, not JS-readable state).
type Listener = () => void

let accessToken: string | null = null
const listeners = new Set<Listener>()

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
  listeners.forEach((listener) => listener())
}

export function subscribeToAccessToken(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}
