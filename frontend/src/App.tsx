import { Stack, Text, Title } from '@mantine/core'
import { Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AccountsPage } from './features/accounts/AccountsPage'
import { AssetsPage } from './features/assets/AssetsPage'
import { useMe } from './features/auth/api'
import { BudgetsPage } from './features/budgets/BudgetsPage'
import { CategoriesPage } from './features/categories/CategoriesPage'
import { GoalsPage } from './features/goals/GoalsPage'
import { MerchantsPage } from './features/merchants/MerchantsPage'
import { TransactionsPage } from './features/transactions/TransactionsPage'
import { LoginPage } from './features/auth/LoginPage'
import { RegisterPage } from './features/auth/RegisterPage'
import { SessionsPage } from './features/auth/SessionsPage'

function Home() {
  const { data: user } = useMe()

  return (
    <Stack>
      <Title order={1}>Dashboard</Title>
      {user && <Text>Welcome, {user.name}.</Text>}
    </Stack>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route path="/budgets" element={<BudgetsPage />} />
          <Route path="/categories" element={<CategoriesPage />} />
          <Route path="/goals" element={<GoalsPage />} />
          <Route path="/merchants" element={<MerchantsPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/settings/sessions" element={<SessionsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
