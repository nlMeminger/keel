import { Code, Stack, Table, Text, TextInput, Title } from '@mantine/core'
import { useState } from 'react'
import { useAuditLog } from './api'

export function AuditLogPage() {
  const [action, setAction] = useState('')
  const { data: entries, isLoading, isError } = useAuditLog({ action })

  return (
    <Stack>
      <Title order={1}>Audit log</Title>
      <TextInput
        label="Filter by action"
        placeholder="e.g. user.suspend"
        value={action}
        onChange={(e) => setAction(e.target.value)}
      />
      {isLoading ? (
        <Text>Loading audit log…</Text>
      ) : isError ? (
        <Text role="alert" c="red">
          Failed to load audit log.
        </Text>
      ) : (
        <Table.ScrollContainer minWidth={800}>
          <Table verticalSpacing="sm">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Time</Table.Th>
                <Table.Th>Admin</Table.Th>
                <Table.Th>Action</Table.Th>
                <Table.Th>Target</Table.Th>
                <Table.Th>Metadata</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {entries?.map((entry) => (
                <Table.Tr key={entry.id}>
                  <Table.Td>{entry.created_at}</Table.Td>
                  <Table.Td>{entry.admin_user_id}</Table.Td>
                  <Table.Td>{entry.action}</Table.Td>
                  <Table.Td>
                    {entry.target_type}
                    {entry.target_id ? `:${entry.target_id}` : ''}
                  </Table.Td>
                  <Table.Td>
                    <Code>{JSON.stringify(entry.metadata)}</Code>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          {entries?.length === 0 && (
            <Text c="dimmed" ta="center" py="md">
              No audit log entries found.
            </Text>
          )}
        </Table.ScrollContainer>
      )}
    </Stack>
  )
}
