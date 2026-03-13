<template>
  <div class="chat-msg" :class="`chat-msg--${message.role}`">
    <div class="chat-msg__bubble">
      <span v-html="formattedContent" />
      <span v-if="streaming" class="chat-msg__cursor">▌</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'

const props = defineProps<{
  message: { role: 'user' | 'assistant'; content: string }
  streaming?: boolean
}>()

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

const formattedContent = computed(() => {
  if (props.message.role === 'assistant') {
    return marked.parse(props.message.content) as string
  }
  return escapeHtml(props.message.content).replace(/\n/g, '<br>')
})
</script>

<style scoped>
.chat-msg {
  display: flex;
  margin-bottom: 12px;
}

.chat-msg--user {
  justify-content: flex-end;
}

.chat-msg--assistant {
  justify-content: flex-start;
}

.chat-msg__bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.chat-msg--user .chat-msg__bubble {
  background: #4a6fa5;
  color: #fff;
  border-bottom-right-radius: 4px;
  white-space: pre-wrap;
}

.chat-msg--assistant .chat-msg__bubble {
  background: #fff;
  color: #2c2416;
  border: 1px solid #e0d8c8;
  border-bottom-left-radius: 4px;
}

/* Markdown要素のスタイル */
.chat-msg--assistant .chat-msg__bubble :deep(p) {
  margin: 0 0 8px;
}
.chat-msg--assistant .chat-msg__bubble :deep(p:last-child) {
  margin-bottom: 0;
}
.chat-msg--assistant .chat-msg__bubble :deep(h1),
.chat-msg--assistant .chat-msg__bubble :deep(h2),
.chat-msg--assistant .chat-msg__bubble :deep(h3) {
  font-weight: bold;
  margin: 12px 0 6px;
  line-height: 1.4;
}
.chat-msg--assistant .chat-msg__bubble :deep(h1) { font-size: 15px; }
.chat-msg--assistant .chat-msg__bubble :deep(h2) { font-size: 14px; }
.chat-msg--assistant .chat-msg__bubble :deep(h3) { font-size: 13px; }
.chat-msg--assistant .chat-msg__bubble :deep(ul),
.chat-msg--assistant .chat-msg__bubble :deep(ol) {
  margin: 6px 0;
  padding-left: 20px;
}
.chat-msg--assistant .chat-msg__bubble :deep(li) {
  margin-bottom: 3px;
}
.chat-msg--assistant .chat-msg__bubble :deep(code) {
  background: #f0ece0;
  border-radius: 3px;
  padding: 1px 5px;
  font-family: monospace;
  font-size: 12px;
}
.chat-msg--assistant .chat-msg__bubble :deep(pre) {
  background: #2c2416;
  color: #f0ece0;
  border-radius: 6px;
  padding: 10px 12px;
  overflow-x: auto;
  margin: 8px 0;
}
.chat-msg--assistant .chat-msg__bubble :deep(pre code) {
  background: none;
  padding: 0;
  color: inherit;
  font-size: 12px;
}
.chat-msg--assistant .chat-msg__bubble :deep(strong) {
  font-weight: bold;
}
.chat-msg--assistant .chat-msg__bubble :deep(em) {
  font-style: italic;
}
.chat-msg--assistant .chat-msg__bubble :deep(blockquote) {
  border-left: 3px solid #c8b89a;
  margin: 6px 0;
  padding-left: 10px;
  color: #7a6a55;
}
.chat-msg--assistant .chat-msg__bubble :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12px;
}
.chat-msg--assistant .chat-msg__bubble :deep(th),
.chat-msg--assistant .chat-msg__bubble :deep(td) {
  border: 1px solid #e0d8c8;
  padding: 4px 8px;
}
.chat-msg--assistant .chat-msg__bubble :deep(th) {
  background: #f0ece0;
  font-weight: bold;
}

.chat-msg__cursor {
  display: inline-block;
  animation: blink 0.8s step-end infinite;
  margin-left: 2px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0; }
}
</style>
