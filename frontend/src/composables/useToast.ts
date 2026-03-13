import { ref } from 'vue'

export interface Toast {
  id: number
  message: string
  type: 'error' | 'success'
}

let nextId = 0
const toasts = ref<Toast[]>([])

export function useToast() {
  function add(message: string, type: Toast['type'], duration?: number) {
    const id = nextId++
    toasts.value.push({ id, message, type })
    const ms = duration ?? (type === 'error' ? 0 : 4000)
    if (ms > 0) {
      setTimeout(() => remove(id), ms)
    }
  }

  function remove(id: number) {
    const idx = toasts.value.findIndex((t) => t.id === id)
    if (idx !== -1) toasts.value.splice(idx, 1)
  }

  return {
    toasts,
    showError: (message: string, duration?: number) => add(message, 'error', duration),
    showSuccess: (message: string, duration?: number) => add(message, 'success', duration),
    remove,
  }
}
