import { Anchor, Button, Paper, PasswordInput, Stack, Text, TextInput, Title } from '@mantine/core'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../../lib/api-client'
import { useRegister } from './api'

export function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const navigate = useNavigate()
  const register = useRegister()

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    register.mutate(
      { email, password, name },
      {
        onSuccess: () => navigate('/login'),
      },
    )
  }

  return (
    <Stack align="center" justify="center" mih="100vh" p="md">
      <Paper withBorder shadow="sm" p="xl" radius="md" w={360}>
        <Title order={1} size="h2" ta="center" mb="lg">
          Register
        </Title>
        <form onSubmit={handleSubmit}>
          <Stack>
            <TextInput
              label="Name"
              value={name}
              onChange={(event) => setName(event.currentTarget.value)}
              required
            />
            <TextInput
              label="Email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.currentTarget.value)}
              required
            />
            <PasswordInput
              label="Password"
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.currentTarget.value)}
              required
            />
            {register.isError && (
              <Text role="alert" c="red" size="sm">
                {register.error instanceof ApiError
                  ? register.error.message
                  : 'Registration failed.'}
              </Text>
            )}
            <Button type="submit" loading={register.isPending} fullWidth>
              Register
            </Button>
          </Stack>
        </form>
        <Text size="sm" ta="center" mt="md">
          Already have an account?{' '}
          <Anchor component={Link} to="/login">
            Log in
          </Anchor>
        </Text>
      </Paper>
    </Stack>
  )
}
