import { Route, Routes } from 'react-router-dom'
import { Landing } from './pages/Landing'
import { AppShell } from './pages/AppShell'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/app" element={<AppShell />} />
      <Route path="/app/*" element={<AppShell />} />
      <Route path="*" element={<Landing />} />
    </Routes>
  )
}