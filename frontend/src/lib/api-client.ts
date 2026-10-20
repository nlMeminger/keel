import { getAccessToken, setAccessToken } from './auth'

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api/v1'

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function parseErrorEnvelope(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { error?: { code: string; message: string } }
    if (body.error) {
      return new ApiError(response.status, body.error.code, body.error.message)
    }
  } catch {
    // Fall through to a generic error below.
  }
  return new ApiError(response.status, 'unknown_error', `Request failed with ${response.status}`)
}

async function parseSuccessBody<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

function buildRequest(options: RequestInit): RequestInit {
  const token = getAccessToken()
  return {
    ...options,
    credentials: 'include',
    headers: {
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  }
}

let refreshInFlight: Promise<boolean> | null = null

/** Silently exchanges the httpOnly refresh cookie for a new access token. Coalesces concurrent calls. */
export async function refreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight

  refreshInFlight = (async () => {
    try {
      const response = await fetch(`${BASE_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      })
      if (!response.ok) {
        setAccessToken(null)
        return false
      }
      const body = (await response.json()) as { data: { access_token: string } }
      setAccessToken(body.data.access_token)
      return true
    } catch {
      setAccessToken(null)
      return false
    }
  })()

  try {
    return await refreshInFlight
  } finally {
    refreshInFlight = null
  }
}

interface ApiFetchOptions extends RequestInit {
  /** Skip the automatic 401-refresh-retry — used by the refresh call itself to avoid a loop. */
  skipAuthRetry?: boolean
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { skipAuthRetry, ...rest } = options
  let response = await fetch(`${BASE_URL}${path}`, buildRequest(rest))

  if (response.status === 401 && !skipAuthRetry) {
    const refreshed = await refreshAccessToken()
    if (refreshed) {
      response = await fetch(`${BASE_URL}${path}`, buildRequest(rest))
    }
  }

  if (!response.ok) {
    throw await parseErrorEnvelope(response)
  }
  return parseSuccessBody<T>(response)
}
