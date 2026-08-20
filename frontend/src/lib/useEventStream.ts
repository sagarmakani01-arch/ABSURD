/**
 * Live event stream — subscribes to the gateway WebSocket and keeps a
 * rolling buffer of the latest events so the UI can reconstruct execution
 * history as it happens.
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import type { SimEvent } from '../types/api'

const MAX_BUFFER = 200

export interface StreamState {
  connected: boolean
  events: SimEvent[]
  lastEvent: SimEvent | null
}

/** URL resolution: same-origin `/ws` in dev is proxied by Vite. */
function wsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${window.location.host}/ws`
}

export function useEventStream(): StreamState {
  const [connected, setConnected] = useState(false)
  const [events, setEvents] = useState<SimEvent[]>([])
  const socketRef = useRef<WebSocket | null>(null)
  const retryRef = useRef(0)

  const lastEvent = useMemo(() => events[events.length - 1] ?? null, [events])

  useEffect(() => {
    let disposed = false
    let socket: WebSocket | null = null

    const connect = () => {
      if (disposed) return
      socket = new WebSocket(wsUrl())
      socketRef.current = socket

      socket.onopen = () => {
        retryRef.current = 0
        setConnected(true)
        socket?.send(JSON.stringify({ type: 'hello', payload: { client: 'app-shell' } }))
      }

      socket.onmessage = (msg) => {
        try {
          const data = JSON.parse(msg.data) as SimEvent
          setEvents((prev) => [...prev.slice(-(MAX_BUFFER - 1)), data])
        } catch {
          /* ignore malformed frames */
        }
      }

      socket.onclose = () => {
        setConnected(false)
        if (!disposed) {
          const backoff = Math.min(30_000, 1000 * 2 ** retryRef.current)
          retryRef.current += 1
          setTimeout(connect, backoff)
        }
      }

      socket.onerror = () => socket?.close()
    }

    connect()

    const heartbeat = setInterval(() => {
      if (socketRef.current?.readyState === WebSocket.OPEN) {
        socketRef.current.send(JSON.stringify({ type: 'ping', payload: {} }))
      }
    }, 25_000)

    return () => {
      disposed = true
      clearInterval(heartbeat)
      socket?.close()
    }
  }, [])

  return { connected, events, lastEvent }
}