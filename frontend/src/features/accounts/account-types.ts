export const ACCOUNT_TYPES = [
  'checking',
  'savings',
  'credit_card',
  'investment',
  'loan',
  'mortgage',
  'student_loan',
] as const

export type AccountType = (typeof ACCOUNT_TYPES)[number]

export const DETAIL_FIELDS: Record<
  AccountType,
  { key: string; label: string; required?: boolean }[]
> = {
  checking: [{ key: 'overdraft_limit', label: 'Overdraft limit' }],
  savings: [{ key: 'interest_rate', label: 'Interest rate (%)' }],
  credit_card: [
    { key: 'credit_limit', label: 'Credit limit', required: true },
    { key: 'apr', label: 'APR (%)' },
  ],
  investment: [{ key: 'account_subtype', label: 'Subtype (e.g. brokerage, 401k)' }],
  loan: [
    { key: 'principal', label: 'Principal', required: true },
    { key: 'interest_rate', label: 'Interest rate (%)' },
    { key: 'term_months', label: 'Term (months)' },
  ],
  mortgage: [
    { key: 'principal', label: 'Principal', required: true },
    { key: 'interest_rate', label: 'Interest rate (%)' },
    { key: 'term_months', label: 'Term (months)' },
    { key: 'escrow_balance', label: 'Escrow balance' },
  ],
  student_loan: [
    { key: 'principal', label: 'Principal', required: true },
    { key: 'interest_rate', label: 'Interest rate (%)' },
    { key: 'servicer', label: 'Servicer' },
  ],
}
