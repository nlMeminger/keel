import { Badge, Button, Group, Paper, Stack, Text, Title } from '@mantine/core'
import { useRevokeOtherSessions, useRevokeSession, useSessions } from './api'

export function SessionsPage() {
  const { data: sessions, isLoading } = useSessions()
  const revokeSession = useRevokeSession()
  const revokeOthers = useRevokeOtherSessions()

  if (isLoading || !sessions) {
    return <Text>Loading sessions…</Text>
  }

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={1} size="h2">
          Active sessions
        </Title>
        <Button
          variant="light"
          color="red"
          onClick={() => revokeOthers.mutate()}
          loading={revokeOthers.isPending}
        >
          Log out everywhere else
        </Button>
      </Group>
      <Stack gap="sm">
        {sessions.map((session) => (
          <Paper key={session.id} withBorder p="md" radius="md">
            <Group justify="space-between">
              <div>
                <Group gap="xs">
                  <Text fw={500}>{session.user_agent ?? 'Unknown device'}</Text>
                  {session.is_current && <Badge size="sm">this session</Badge>}
                </Group>
                <Text size="sm" c="dimmed">
                  Created {new Date(session.created_at).toLocaleString()}
                </Text>
              </div>
              {!session.is_current && (
                <Button
                  variant="subtle"
                  color="red"
                  onClick={() => revokeSession.mutate(session.id)}
                  loading={revokeSession.isPending}
                >
                  Revoke
                </Button>
              )}
            </Group>
          </Paper>
        ))}
      </Stack>
    </Stack>
  )
}
