import { Badge, Button, Group, NativeSelect, Stack, Table, Text, Title } from '@mantine/core'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { type AdminUser, useAdminUsers, useUpdateAdminUser } from './api'

const STATUS_COLOR: Record<string, string> = { active: 'teal', suspended: 'red' }

function SuspendToggle({ user }: { user: AdminUser }) {
  const updateUser = useUpdateAdminUser(user.id)
  const isSuspended = user.status === 'suspended'

  return (
    <Button
      size="xs"
      variant="subtle"
      color={isSuspended ? 'teal' : 'red'}
      onClick={() => updateUser.mutate({ status: isSuspended ? 'active' : 'suspended' })}
      loading={updateUser.isPending}
    >
      {isSuspended ? 'Activate' : 'Suspend'}
    </Button>
  )
}

export function UsersPage() {
  const [role, setRole] = useState('')
  const [status, setStatus] = useState('')
  const { data: users, isLoading, isError } = useAdminUsers({ role, status })

  return (
    <Stack>
      <Title order={1}>Users</Title>
      <Group>
        <NativeSelect
          label="Role"
          value={role}
          onChange={(e) => setRole(e.target.value)}
          data={[
            { value: '', label: 'All roles' },
            { value: 'user', label: 'User' },
            { value: 'admin', label: 'Admin' },
          ]}
        />
        <NativeSelect
          label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          data={[
            { value: '', label: 'All statuses' },
            { value: 'active', label: 'Active' },
            { value: 'suspended', label: 'Suspended' },
          ]}
        />
      </Group>
      {isLoading ? (
        <Text>Loading users…</Text>
      ) : isError ? (
        <Text role="alert" c="red">
          Failed to load users.
        </Text>
      ) : (
        <Table.ScrollContainer minWidth={700}>
          <Table verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Email</Table.Th>
                <Table.Th>Name</Table.Th>
                <Table.Th>Role</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Linked banks</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {users?.map((user) => (
                <Table.Tr key={user.id}>
                  <Table.Td>
                    <Text component={Link} to={`/admin/users/${user.id}`} fw={500}>
                      {user.email}
                    </Text>
                  </Table.Td>
                  <Table.Td>{user.name}</Table.Td>
                  <Table.Td>{user.role}</Table.Td>
                  <Table.Td>
                    <Badge color={STATUS_COLOR[user.status]} variant="light">
                      {user.status}
                    </Badge>
                  </Table.Td>
                  <Table.Td>{user.linked_bank_count}</Table.Td>
                  <Table.Td>
                    <SuspendToggle user={user} />
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          {users?.length === 0 && (
            <Text c="dimmed" ta="center" py="md">
              No users found.
            </Text>
          )}
        </Table.ScrollContainer>
      )}
    </Stack>
  )
}
