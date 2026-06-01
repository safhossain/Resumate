<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { useSessionStore, sanitizeKey } from '../stores/session'

const session = useSessionStore()

/* ── autoscroll ───────────────────────────────────────────────────── */
const autoscroll = ref(true)
const listEl = ref<HTMLUListElement | null>(null)

watch(
  () => session.placeholderList.length,
  async () => {
    if (!autoscroll.value || !listEl.value) return
    await nextTick()
    listEl.value.scrollTop = listEl.value.scrollHeight
  },
)

/* ── per-row rename state ─────────────────────────────────────────── */
const editingKey = ref<string | null>(null)
const editValue  = ref('')
const editError  = ref('')

function startRename(key: string) {
  editingKey.value = key
  editValue.value  = key
  editError.value  = ''
}

function onEditInput(raw: string) {
  editValue.value = raw
  const clean = sanitizeKey(raw)
  if (!clean) {
    editError.value = 'Key cannot be empty.'
  } else if (
    clean !== editingKey.value &&
    Object.keys(session.placeholders).includes(clean)
  ) {
    editError.value = `'${clean}' already exists.`
  } else {
    editError.value = ''
  }
}

async function commitRename() {
  if (!editingKey.value) return
  const clean = sanitizeKey(editValue.value)
  if (!clean || editError.value) return
  if (clean === editingKey.value) { cancelRename(); return }
  try {
    await session.renamePlaceholder(editingKey.value, clean)
  } catch (e: unknown) {
    editError.value = e instanceof Error ? e.message : String(e)
    return
  }
  cancelRename()
}

function cancelRename() {
  editingKey.value = null
  editValue.value  = ''
  editError.value  = ''
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter')  commitRename()
  if (e.key === 'Escape') cancelRename()
}

/* ── placeholder download ────────────────────────────────────────── */
function downloadJson(obj: Record<string, string>, filename: string) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function downloadPlaceholders() {
  const fields: Record<string, string> = {}
  const sensitiveFields: Record<string, string> = {}
  for (const ph of session.placeholderList) {
    if (ph.type === 'tailor') {
      fields[ph.key] = ph.selected_text
    } else {
      sensitiveFields[ph.key] = ph.value ?? ph.selected_text
    }
  }
  if (Object.keys(fields).length) downloadJson(fields, 'fields.json')
  if (Object.keys(sensitiveFields).length) downloadJson(sensitiveFields, 'sensitive_fields.json')
}
</script>

<template>
  <div class="p-4 border-b border-gray-800" v-if="session.placeholderList.length">
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-1.5">
        <p class="text-xs text-gray-500 uppercase tracking-wider">Placeholders</p>
        <button
          class="flex items-center justify-center w-5 h-5 rounded text-gray-600 hover:text-blue-400 hover:bg-gray-700/50 transition-colors"
          title="Download fields.json and sensitive_fields.json"
          @click="downloadPlaceholders"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3.5 h-3.5">
            <path d="M8 1a.75.75 0 0 1 .75.75v6.19l1.97-1.97a.75.75 0 1 1 1.06 1.06l-3.25 3.25a.75.75 0 0 1-1.06 0L4.22 7.03a.75.75 0 1 1 1.06-1.06L7.25 7.94V1.75A.75.75 0 0 1 8 1ZM2.75 13a.75.75 0 0 0 0 1.5h10.5a.75.75 0 0 0 0-1.5H2.75Z"/>
          </svg>
        </button>
      </div>
      <label
        class="flex items-center gap-1.5 text-[10px] text-gray-600 cursor-pointer select-none"
        title="Scroll to the newest placeholder when one is added"
      >
        <input
          v-model="autoscroll"
          type="checkbox"
          class="accent-blue-500 w-3 h-3"
        />
        Autoscroll
      </label>
    </div>

    <ul ref="listEl" class="space-y-1.5 max-h-56 overflow-y-auto">
      <li
        v-for="ph in session.placeholderList"
        :key="ph.key"
        class="flex items-start gap-2 text-sm px-2 py-1.5 rounded bg-gray-800/40"
      >
        <!-- type toggle -->
        <button
          class="mt-0.5 w-4 h-4 rounded-full flex-shrink-0 flex items-center justify-center transition-colors"
          :class="ph.type === 'tailor' ? 'bg-blue-500/30 hover:bg-amber-500/30' : 'bg-amber-500/30 hover:bg-blue-500/30'"
          :title="`Switch to ${ph.type === 'tailor' ? 'sensitive' : 'tailor'}`"
          @click="session.togglePlaceholderType(ph.key)"
        >
          <span
            class="w-2 h-2 rounded-full"
            :class="ph.type === 'tailor' ? 'bg-blue-500' : 'bg-amber-500'"
          />
        </button>

        <div class="flex-1 min-w-0">
          <!-- key: normal display or inline rename field -->
          <div v-if="editingKey === ph.key" class="mb-0.5">
            <input
              :value="editValue"
              autofocus
              class="w-full font-mono text-xs bg-gray-900 border rounded px-1.5 py-0.5 focus:outline-none focus:ring-1"
              :class="editError
                ? 'border-red-500 text-red-300 focus:ring-red-500'
                : 'border-gray-600 text-gray-200 focus:ring-blue-500'"
              @input="onEditInput(($event.target as HTMLInputElement).value)"
              @keydown="onKeydown"
              @blur="commitRename"
            />
            <p v-if="editError" class="text-[10px] text-red-400 mt-0.5">{{ editError }}</p>
            <p v-else-if="editValue !== sanitizeKey(editValue)" class="text-[10px] text-gray-500 mt-0.5">
              Will save as: <span class="text-gray-300 font-mono">{{ sanitizeKey(editValue) }}</span>
            </p>
          </div>
          <button
            v-else
            class="font-mono text-xs text-left w-full truncate hover:underline decoration-dotted"
            :class="ph.type === 'tailor' ? 'text-blue-400' : 'text-amber-400'"
            title="Click to rename"
            @click="startRename(ph.key)"
          >
            {{ ph.key }}
          </button>

          <!-- selected text preview -->
          <p class="text-[11px] text-gray-500 truncate mt-0.5">{{ ph.selected_text }}</p>

          <!-- editable value for sensitive -->
          <input
            v-if="ph.type === 'sensitive'"
            :value="ph.value ?? ph.selected_text"
            placeholder="Enter real value…"
            class="mt-1 w-full text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-amber-300 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-amber-500"
            @input="
              (e) =>
                session.updatePlaceholderValue(
                  ph.key,
                  (e.target as HTMLInputElement).value,
                )
            "
          />
        </div>

        <!-- remove -->
        <button
          class="text-gray-600 hover:text-red-400 text-xs flex-shrink-0 transition-colors"
          title="Remove placeholder"
          @click="session.removePlaceholder(ph.key)"
        >
          ✕
        </button>
      </li>
    </ul>
  </div>
</template>
