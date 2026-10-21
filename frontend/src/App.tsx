import { Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AccountDetailPage } from './features/accounts/AccountDetailPage'
import { AccountsPage } from './features/accounts/AccountsPage'
import { AssetsPage } from './features/assets/AssetsPage'
import { BankDetailPage } from './features/banks/BankDetailPage'
import { BanksPage } from './features/banks/BanksPage'
import { BudgetsPage } from './features/budgets/BudgetsPage'
import { CategoriesPage } from './features/categories/CategoriesPage'
import { CategoryRulesPage } from './features/category-rules/CategoryRulesPage'
import { DashboardPage } from './features/dashboard/DashboardPage'
import { GoalsPage } from './features/goals/GoalsPage'
import { MerchantsPage } from './features/merchants/MerchantsPage'
import { NotificationsPage } from './features/notifications/NotificationsPage'
import { RecurringTransactionsPage } from './features/recurring-transactions/RecurringTransactionsPage'
import { ReportsPage } from './features/reports/ReportsPage'
import { TransactionsPage } from './features/transactions/TransactionsPage'
import { LoginPage } from './features/auth/LoginPage'
import { RegisterPage } from './features/auth/RegisterPage'
import { SessionsPage } from './features/auth/SessionsPage'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/banks" element={<BanksPage />} />
          <Route path="/banks/:bankId" element={<BankDetailPage />} />
          <Route path="/accounts" element={<AccountsPage />} />
          <Route path="/accounts/:accountId" element={<AccountDetailPage />} />
          <Route path="/assets" element={<AssetsPage />} />
          <Route path="/budgets" element={<BudgetsPage />} />
          <Route path="/categories" element={<CategoriesPage />} />
          <Route path="/category-rules" element={<CategoryRulesPage />} />
          <Route path="/goals" element={<GoalsPage />} />
          <Route path="/merchants" element={<MerchantsPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="/recurring-transactions" element={<RecurringTransactionsPage />} />
          <Route path="/transactions" element={<TransactionsPage />} />
          <Route path="/settings/sessions" element={<SessionsPage />} />
        </Route>
      </Route>
    </Routes>
  )
}

export default App
