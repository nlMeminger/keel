import { Link, Route, Routes, useNavigate } from 'react-router-dom'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AccountsPage } from './features/accounts/AccountsPage'
import { AssetsPage } from './features/assets/AssetsPage'
import { useLogout, useMe } from './features/auth/api'
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
  const logout = useLogout()
  const navigate = useNavigate()

  return (
    <main>
      <h1>Money App</h1>
      {user && <p>Welcome, {user.name}.</p>}
      <nav>
        <Link to="/accounts">Accounts</Link>
        <Link to="/assets">Assets</Link>
        <Link to="/budgets">Budgets</Link>
        <Link to="/categories">Categories</Link>
        <Link to="/goals">Goals</Link>
        <Link to="/merchants">Merchants</Link>
        <Link to="/transactions">Transactions</Link>
        <Link to="/settings/sessions">Sessions</Link>
      </nav>
      <button
        type="button"
        onClick={() => logout.mutate(undefined, { onSuccess: () => navigate('/login') })}
        disabled={logout.isPending}
      >
        Log out
      </button>
    </main>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
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
    </Routes>
  )
}

export default App
