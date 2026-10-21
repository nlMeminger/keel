import {
  Badge,
  Button,
  Checkbox,
  Group,
  NumberInput,
  Paper,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import {
  useAdminUser,
  useDeleteAdminUser,
  useResetPassword,
  useRevokeSessions,
  useUpdateAdminUser,
  useUpdatePlaidAccess,
} from './api'

const STATUS_COLOR: Record<string, string> = { active: 'teal', suspended: 'red' }

export function UserDetailPage() {
  const { userId } = useParams<{ userId: string }>()
  const navigate = useNavigate()
  const { data: user, isLoading, isError } = useAdminUser(userId ?? '')
  const updateUser = useUpdateAdminUser(userId ?? '')
  const updatePlaidAccess = useUpdatePlaidAccess(userId ?? '')
  const resetPassword = useResetPassword(userId ?? '')
  const revokeSessions = useRevokeSessions(userId ?? '')
  const deleteUser = useDeleteAdminUser()

  const [temporaryPassword, setTemporaryPassword] = useState<string | null>(null)
  const [plaidEnabled, setPlaidEnabled] = useState(true)
  const [monthlyCallLimit, setMonthlyCallLimit] = useState<string | number>('')

  // Hooks must run unconditionally on every render, so the form fields are seeded here
  // (once the user loads) rather than from a conditional useState initializer.
  useEffect(() => {
    if (user) {
      setPlaidEnabled(user.plaid_enabled)
      setMonthlyCallLimit(user.plaid_monthly_call_limit ?? '')
    }
  }, [user])

  if (isLoading || !user) {
    return <Text>Loading user…</Text>
  }
  if (isError) {
    return (
      <Text role="alert" c="red">
        Failed to load user.
      </Text>
    )
  }

  const isSuspended = user.status === 'suspended'

  return (
    <Stack maw={600}>
      <Group justify="space-between">
        <Title order={1}>{user.email}</Title>
        <Badge color={STATUS_COLOR[user.status]} variant="light">
          {user.status}
        </Badge>
      </Group>

      <Paper withBorder p="md" radius="md">
        <Stack gap="xs">
          <Text>
            <Text span fw={500}>
              Name:
            </Text>{' '}
            {user.name}
          </Text>
          <Text>
            <Text span fw={500}>
              Role:
            </Text>{' '}
            {user.role}
          </Text>
          <Text>
            <Text span fw={500}>
              Linked banks:
            </Text>{' '}
            {user.linked_bank_count}
          </Text>
          <Text>
            <Text span fw={500}>
              Plaid calls this month:
            </Text>{' '}
            {user.plaid_calls_this_month}
            {user.plaid_monthly_call_limit !== null ? ` / ${user.plaid_monthly_call_limit}` : ''}
          </Text>
          <Text>
            <Text span fw={500}>
              Created:
            </Text>{' '}
            {user.created_at}
          </Text>
          <Text>
            <Text span fw={500}>
              Last login:
            </Text>{' '}
            {user.last_login_at ?? 'never'}
          </Text>
        </Stack>
      </Paper>

      <Group>
        <Button
          color={isSuspended ? 'teal' : 'red'}
          onClick={() => updateUser.mutate({ status: isSuspended ? 'active' : 'suspended' })}
          loading={updateUser.isPending}
        >
          {isSuspended ? 'Activate user' : 'Suspend user'}
        </Button>
        <Button
          variant="subtle"
          onClick={() =>
            resetPassword.mutate(undefined, {
              onSuccess: (data) => setTemporaryPassword(data.temporary_password),
            })
          }
          loading={resetPassword.isPending}
        >
          Reset password
        </Button>
        <Button
          variant="subtle"
          onClick={() => revokeSessions.mutate()}
          loading={revokeSessions.isPending}
        >
          Revoke sessions
        </Button>
      </Group>
      {temporaryPassword && (
        <Text role="status">Temporary password (shown once): {temporaryPassword}</Text>
      )}
      {revokeSessions.isSuccess && <Text role="status">Sessions revoked.</Text>}

      <Paper withBorder p="md" radius="md">
        <Stack gap="sm">
          <Title order={3} size="h5">
            Plaid access
          </Title>
          <Checkbox
            label="Plaid enabled"
            checked={plaidEnabled}
            onChange={(e) => setPlaidEnabled(e.currentTarget.checked)}
          />
          <NumberInput
            label="Monthly call limit (blank = unlimited)"
            value={monthlyCallLimit}
            onChange={setMonthlyCallLimit}
          />
          <Button
            onClick={() =>
              updatePlaidAccess.mutate({
                enabled: plaidEnabled,
                monthly_call_limit: monthlyCallLimit === '' ? null : Number(monthlyCallLimit),
              })
            }
            loading={updatePlaidAccess.isPending}
          >
            Update Plaid access
          </Button>
        </Stack>
      </Paper>

      <Button
        color="red"
        variant="outline"
        onClick={() => deleteUser.mutate(user.id, { onSuccess: () => navigate('/admin/users') })}
        loading={deleteUser.isPending}
      >
        Delete user
      </Button>
    </Stack>
  )
}
