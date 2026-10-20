import { Route, Routes } from 'react-router-dom'

function Home() {
  return (
    <main>
      <h1>Money App</h1>
    </main>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
    </Routes>
  )
}

export default App
