import { Button, Checkbox, Group, Paper, Stack, Text, Title } from '@mantine/core'
import { useState } from 'react'
import {
  useDismissNotification,
  useNotifications,
  useSetNotificationRead,
  type Notification,
} from './api'

function NotificationRow({ notification }: { notification: Notification }) {
  const setRead = useSetNotificationRead()
  const dismiss = useDismissNotification()
  const isRead = notification.read_at !== null

  return (
    <Paper
      component="li"
      withBorder
      p="md"
      radius="md"
      style={{ listStyle: 'none', opacity: isRead ? 0.6 : 1 }}
    >
      <Group justify="space-between" wrap="nowrap">
        <Stack gap={2}>
          <Text fw={500}>{notification.title}</Text>
          <Text size="sm" c="dimmed">
            {notification.body}
          </Text>
        </Stack>
        <Group gap="xs" wrap="nowrap">
          <Button
            size="sm"
            variant="subtle"
            onClick={() => setRead.mutate({ id: notification.id, read: !isRead })}
            loading={setRead.isPending}
          >
            {isRead ? 'Mark unread' : 'Mark read'}
          </Button>
          <Button
            size="sm"
            variant="subtle"
            color="red"
            onClick={() => dismiss.mutate(notification.id)}
            loading={dismiss.isPending}
          >
            Dismiss
          </Button>
        </Group>
      </Group>
    </Paper>
  )
}

export function NotificationsPage() {
  const [unreadOnly, setUnreadOnly] = useState(false)
  const { data: notifications, isLoading } = useNotifications(unreadOnly)

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={1}>Notifications</Title>
        <Checkbox
          label="Unread only"
          checked={unreadOnly}
          onChange={(e) => setUnreadOnly(e.currentTarget.checked)}
        />
      </Group>
      {isLoading || !notifications ? (
        <Text>Loading notifications…</Text>
      ) : notifications.length === 0 ? (
        <Text c="dimmed">No notifications.</Text>
      ) : (
        <Stack gap="sm" component="ul" style={{ padding: 0 }}>
          {notifications.map((notification) => (
            <NotificationRow key={notification.id} notification={notification} />
          ))}
        </Stack>
      )}
    </Stack>
  )
}
