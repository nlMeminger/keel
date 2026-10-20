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
    <main>
      <h1>Register</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="name">Name</label>
          <input id="name" value={name} onChange={(e) => setName(e.target.value)} required />
        </div>
        <div>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        {register.isError && (
          <p role="alert">
            {register.error instanceof ApiError ? register.error.message : 'Registration failed.'}
          </p>
        )}
        <button type="submit" disabled={register.isPending}>
          {register.isPending ? 'Registering…' : 'Register'}
        </button>
      </form>
      <p>
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </main>
  )
}
