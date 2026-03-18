import axios from 'axios'

const BASE = 'http://localhost:18432/api'

export interface Deck {
  id: number
  name: string
  format: string | null
  created_at: string
  latest_version: DeckVersionSummary | null
}

export interface DeckVersionSummary {
  id: number
  version_number: number
  memo: string | null
  registered_at: string
  main_count: number
  side_count: number
}

export interface CardEntry {
  card_name: string
  quantity: number
  scryfall_id: string | null
}

export interface DeckVersionDetail extends DeckVersionSummary {
  main: CardEntry[]
  sideboard: CardEntry[]
}

export async function fetchDecks(): Promise<Deck[]> {
  const res = await axios.get(`${BASE}/decklist/decks`)
  return res.data
}

export async function createDeck(name: string, format: string | null): Promise<Deck> {
  const res = await axios.post(`${BASE}/decklist/decks`, { name, format })
  return res.data
}

export async function updateDeck(deckId: number, name: string, format: string | null): Promise<Deck> {
  const res = await axios.put(`${BASE}/decklist/decks/${deckId}`, { name, format })
  return res.data
}

export async function deleteDeck(deckId: number): Promise<void> {
  await axios.delete(`${BASE}/decklist/decks/${deckId}`)
}

export async function fetchVersions(deckId: number): Promise<DeckVersionSummary[]> {
  const res = await axios.get(`${BASE}/decklist/decks/${deckId}/versions`)
  return res.data
}

export async function fetchVersion(deckId: number, versionId: number): Promise<DeckVersionDetail> {
  const res = await axios.get(`${BASE}/decklist/decks/${deckId}/versions/${versionId}`)
  return res.data
}

export async function createVersionFromText(
  deckId: number,
  memo: string,
  text: string,
): Promise<DeckVersionDetail> {
  const res = await axios.post(`${BASE}/decklist/decks/${deckId}/versions`, { memo, text })
  return res.data
}

export async function createVersionFromDek(
  deckId: number,
  memo: string,
  file: File,
): Promise<DeckVersionDetail> {
  const form = new FormData()
  form.append('memo', memo)
  form.append('file', file)
  const res = await axios.post(`${BASE}/decklist/decks/${deckId}/versions/import`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function updateVersion(
  deckId: number,
  versionId: number,
  memo: string,
  text: string,
): Promise<DeckVersionDetail> {
  const res = await axios.put(
    `${BASE}/decklist/decks/${deckId}/versions/${versionId}`,
    { memo, text },
  )
  return res.data
}

export async function deleteVersion(deckId: number, versionId: number): Promise<void> {
  await axios.delete(`${BASE}/decklist/decks/${deckId}/versions/${versionId}`)
}

export function cardImageUrl(scryfallId: string, size: 'small' | 'normal' = 'small'): string {
  return `${BASE}/cards/${scryfallId}/image?size=${size}`
}
