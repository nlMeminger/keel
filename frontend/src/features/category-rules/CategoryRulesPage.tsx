import {
  Button,
  Checkbox,
  Group,
  NativeSelect,
  Paper,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useState } from 'react'
import { useAccounts } from '../accounts/api'
import { useCategories } from '../categories/api'
import { useJobPolling } from '../../hooks/use-job-polling'
import {
  useApplyCategoryRules,
  useCreateCategoryRule,
  useDeleteCategoryRule,
  useUpdateCategoryRule,
  type CategoryRule,
  useCategoryRules,
} from './api'

function CreateRuleForm() {
  const { data: categories } = useCategories('all')
  const { data: accounts } = useAccounts()
  const createRule = useCreateCategoryRule()
  const [merchantContains, setMerchantContains] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [accountId, setAccountId] = useState('')
  const [amountMin, setAmountMin] = useState('')
  const [amountMax, setAmountMax] = useState('')
  const [priority, setPriority] = useState('100')

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    createRule.mutate(
      {
        merchant_contains: merchantContains || null,
        amount_min: amountMin || null,
        amount_max: amountMax || null,
        account_id: accountId || null,
        category_id: categoryId,
        priority: Number(priority),
        active: true,
      },
      {
        onSuccess: () => {
          setMerchantContains('')
          setAmountMin('')
          setAmountMax('')
        },
      },
    )
  }

  return (
    <Paper withBorder p="lg" radius="md" component="form" onSubmit={handleSubmit}>
      <Stack>
        <Title order={2} size="h4">
          Add category rule
        </Title>
        <TextInput
          label="Description contains"
          placeholder="e.g. netflix"
          value={merchantContains}
          onChange={(e) => setMerchantContains(e.target.value)}
        />
        <NativeSelect
          label="Assign category"
          value={categoryId}
          onChange={(e) => setCategoryId(e.target.value)}
          data={[
            { value: '', label: 'Select a category' },
            ...(categories ?? []).map((category) => ({
              value: category.id,
              label: category.primary_category,
            })),
          ]}
          required
        />
        <NativeSelect
          label="Limit to account"
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
          data={[
            { value: '', label: 'Any account' },
            ...(accounts ?? []).map((account) => ({ value: account.id, label: account.name })),
          ]}
        />
        <Group grow>
          <TextInput
            label="Min amount"
            type="number"
            step="0.01"
            value={amountMin}
            onChange={(e) => setAmountMin(e.target.value)}
          />
          <TextInput
            label="Max amount"
            type="number"
            step="0.01"
            value={amountMax}
            onChange={(e) => setAmountMax(e.target.value)}
          />
          <TextInput
            label="Priority"
            type="number"
            value={priority}
            onChange={(e) => setPriority(e.target.value)}
          />
        </Group>
        <Button type="submit" loading={createRule.isPending} disabled={!categoryId}>
          Add rule
        </Button>
      </Stack>
    </Paper>
  )
}

function RuleRow({ rule, categoryName }: { rule: CategoryRule; categoryName: string }) {
  const updateRule = useUpdateCategoryRule()
  const deleteRule = useDeleteCategoryRule()

  const conditions = [
    rule.merchant_contains && `description contains "${rule.merchant_contains}"`,
    rule.amount_min != null && `amount ≥ ${rule.amount_min}`,
    rule.amount_max != null && `amount ≤ ${rule.amount_max}`,
  ].filter(Boolean)

  return (
    <Paper component="li" withBorder p="md" radius="md" style={{ listStyle: 'none' }}>
      <Group justify="space-between" wrap="nowrap">
        <Stack gap={2}>
          <Text fw={500}>→ {categoryName}</Text>
          <Text size="sm" c="dimmed">
            {conditions.length > 0 ? conditions.join(', ') : 'Matches every transaction'} (priority{' '}
            {rule.priority})
          </Text>
        </Stack>
        <Group gap="xs" wrap="nowrap">
          <Checkbox
            label="Active"
            checked={rule.active}
            onChange={(e) =>
              updateRule.mutate({ id: rule.id, input: { active: e.currentTarget.checked } })
            }
          />
          <Button
            size="sm"
            variant="subtle"
            color="red"
            onClick={() => deleteRule.mutate(rule.id)}
            loading={deleteRule.isPending}
          >
            Delete
          </Button>
        </Group>
      </Group>
    </Paper>
  )
}

function ApplyRulesSection() {
  const applyRules = useApplyCategoryRules()
  const [jobId, setJobId] = useState<string | null>(null)
  const { data: job } = useJobPolling(jobId)

  return (
    <Group>
      <Button
        variant="light"
        loading={applyRules.isPending}
        onClick={() => applyRules.mutate(undefined, { onSuccess: setJobId })}
      >
        Apply rules to uncategorized transactions
      </Button>
      {job?.status === 'succeeded' && <Text c="teal">Done — transactions updated.</Text>}
      {job?.status === 'failed' && <Text c="red">Failed: {job.error}</Text>}
      {(job?.status === 'pending' || job?.status === 'running') && (
        <Text c="dimmed">Applying…</Text>
      )}
    </Group>
  )
}

export function CategoryRulesPage() {
  const { data: categories } = useCategories('all')
  const { data: rules, isLoading } = useCategoryRules()
  const categoryNames = new Map((categories ?? []).map((c) => [c.id, c.primary_category]))

  return (
    <Stack>
      <Title order={1}>Category rules</Title>
      <CreateRuleForm />
      <ApplyRulesSection />
      {isLoading || !rules ? (
        <Text>Loading category rules…</Text>
      ) : (
        <Stack gap="sm" component="ul" style={{ padding: 0 }}>
          {rules.map((rule) => (
            <RuleRow
              key={rule.id}
              rule={rule}
              categoryName={categoryNames.get(rule.category_id) ?? ''}
            />
          ))}
        </Stack>
      )}
    </Stack>
  )
}
