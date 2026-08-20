import { Route, Routes } from 'react-router-dom'
import { Landing } from './pages/Landing'
import { AppLayout } from './app/AppLayout'
import { Overview } from './pages/app/Overview'
import { Tools } from './pages/app/Tools'
import { ToolDetail } from './pages/app/ToolDetail'
import { Tasks } from './pages/app/Tasks'
import { Experiments } from './pages/app/Experiments'
import { Memory } from './pages/app/Memory'
import { Evaluation } from './pages/app/Evaluation'
import { System } from './pages/app/System'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 0,
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/app" element={<AppLayout />}>
          <Route index element={<Overview />} />
          <Route path="tools" element={<Tools />} />
          <Route path="tools/:id" element={<ToolDetail />} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="experiments" element={<Experiments />} />
          <Route path="memory" element={<Memory />} />
          <Route path="evaluation" element={<Evaluation />} />
          <Route path="system" element={<System />} />
        </Route>
        <Route path="*" element={<Landing />} />
      </Routes>
    </QueryClientProvider>
  )
}