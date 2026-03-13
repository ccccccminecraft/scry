import client from './client'
export type { PromptTemplate, QuestionSet, QuestionItem } from './analysis'

export interface PromptTemplateInput {
  name: string
  content: string
  is_default: boolean
}

export interface QuestionItemInput {
  text: string
  display_order: number
}

export interface QuestionSetInput {
  name: string
  is_default: boolean
  items: QuestionItemInput[]
}

export async function createPromptTemplate(body: PromptTemplateInput) {
  const res = await client.post('/api/prompt-templates', body)
  return res.data
}

export async function updatePromptTemplate(id: number, body: PromptTemplateInput) {
  const res = await client.put(`/api/prompt-templates/${id}`, body)
  return res.data
}

export async function deletePromptTemplate(id: number): Promise<void> {
  await client.delete(`/api/prompt-templates/${id}`)
}

export async function createQuestionSet(body: QuestionSetInput) {
  const res = await client.post('/api/question-sets', body)
  return res.data
}

export async function updateQuestionSet(id: number, body: QuestionSetInput) {
  const res = await client.put(`/api/question-sets/${id}`, body)
  return res.data
}

export async function deleteQuestionSet(id: number): Promise<void> {
  await client.delete(`/api/question-sets/${id}`)
}
