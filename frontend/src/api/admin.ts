import axios from 'axios'

const BASE = 'http://localhost:18432/api'

export async function getSyncStatus(): Promise<{ last_synced_at: string | null }> {
  const res = await axios.get(`${BASE}/admin/sync-card-names/status`)
  return res.data
}

export async function syncCardNames(): Promise<{ synced: number }> {
  const res = await axios.post(`${BASE}/admin/sync-card-names`)
  return res.data
}
