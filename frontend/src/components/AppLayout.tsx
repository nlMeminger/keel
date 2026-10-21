import {
  ActionIcon,
  AppShell,
  Burger,
  Group,
  Menu,
  NavLink,
  Stack,
  Title,
  useComputedColorScheme,
  useMantineColorScheme,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconArrowsLeftRight,
  IconBell,
  IconBuildingBank,
  IconBuildingStore,
  IconCalendarRepeat,
  IconChartPie,
  IconChevronDown,
  IconDevices,
  IconLayoutDashboard,
  IconLogout,
  IconMoon,
  IconPigMoney,
  IconReportAnalytics,
  IconSun,
  IconTags,
  IconTarget,
  IconWallet,
  IconWand,
} from '@tabler/icons-react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useLogout, useMe } from '../features/auth/api'

const navItems = [
  { to: '/', label: 'Dashboard', icon: IconLayoutDashboard },
  { to: '/reports', label: 'Reports', icon: IconReportAnalytics },
  { to: '/banks', label: 'Banks', icon: IconBuildingBank },
  { to: '/accounts', label: 'Accounts', icon: IconWallet },
  { to: '/transactions', label: 'Transactions', icon: IconArrowsLeftRight },
  { to: '/categories', label: 'Categories', icon: IconTags },
  { to: '/category-rules', label: 'Category rules', icon: IconWand },
  { to: '/merchants', label: 'Merchants', icon: IconBuildingStore },
  { to: '/budgets', label: 'Budgets', icon: IconChartPie },
  { to: '/goals', label: 'Goals', icon: IconTarget },
  { to: '/recurring-transactions', label: 'Recurring', icon: IconCalendarRepeat },
  { to: '/assets', label: 'Assets', icon: IconPigMoney },
  { to: '/notifications', label: 'Notifications', icon: IconBell },
  { to: '/settings/sessions', label: 'Sessions', icon: IconDevices },
]

export function AppLayout() {
  const [opened, { toggle, close }] = useDisclosure()
  const { setColorScheme } = useMantineColorScheme()
  const computedColorScheme = useComputedColorScheme('light')
  const location = useLocation()
  const navigate = useNavigate()
  const { data: user } = useMe()
  const logout = useLogout()

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 240, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group>
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <Title order={3}>Keel</Title>
          </Group>
          <Group gap="xs">
            <ActionIcon
              variant="subtle"
              aria-label="Toggle color scheme"
              onClick={() => setColorScheme(computedColorScheme === 'dark' ? 'light' : 'dark')}
            >
              {computedColorScheme === 'dark' ? <IconSun size={18} /> : <IconMoon size={18} />}
            </ActionIcon>
            <Menu position="bottom-end">
              <Menu.Target>
                <ActionIcon variant="subtle" aria-label="Account menu">
                  <IconChevronDown size={18} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                {user && <Menu.Label>{user.name}</Menu.Label>}
                <Menu.Item
                  leftSection={<IconLogout size={16} />}
                  onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}
                >
                  Log out
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="md">
        <Stack gap={4}>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              component={Link}
              to={item.to}
              label={item.label}
              leftSection={<item.icon size={18} />}
              active={location.pathname === item.to || location.pathname.startsWith(`${item.to}/`)}
              onClick={close}
            />
          ))}
        </Stack>
      </AppShell.Navbar>
      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}
