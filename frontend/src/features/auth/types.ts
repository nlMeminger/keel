export interface User {
  id: string
  email: string
  name: string
  timezone: string
  role: string
  status: string
  must_change_password: boolean
  created_at: string
}

export interface SessionSummary {
  id: string
  created_at: string
  last_used_at: string | null
  user_agent: string | null
  is_current: boolean
}
