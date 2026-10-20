import { useRevokeOtherSessions, useRevokeSession, useSessions } from './api'

export function SessionsPage() {
  const { data: sessions, isLoading } = useSessions()
  const revokeSession = useRevokeSession()
  const revokeOthers = useRevokeOtherSessions()

  if (isLoading || !sessions) {
    return <p>Loading sessions…</p>
  }

  return (
    <main>
      <h1>Active sessions</h1>
      <button type="button" onClick={() => revokeOthers.mutate()} disabled={revokeOthers.isPending}>
        Log out everywhere else
      </button>
      <ul>
        {sessions.map((session) => (
          <li key={session.id}>
            {session.user_agent ?? 'Unknown device'}
            {session.is_current ? ' (this session)' : ''} — created{' '}
            {new Date(session.created_at).toLocaleString()}
            {!session.is_current && (
              <button
                type="button"
                onClick={() => revokeSession.mutate(session.id)}
                disabled={revokeSession.isPending}
              >
                Revoke
              </button>
            )}
          </li>
        ))}
      </ul>
    </main>
  )
}
