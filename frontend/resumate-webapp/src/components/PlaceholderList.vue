<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
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

/* ── scroll-into-view on highlight click ──────────────────────────────
 * When a highlight is clicked in the document viewer, the session store
 * emits a `scrollRequest`. Scroll the matching row to the top of the list;
 * the browser clamps scrollTop to its max, so rows near the bottom simply
 * become visible instead of being forced to the (impossible) top. */
watch(
  () => session.scrollRequest,
  async (req) => {
    const ul = listEl.value
    if (!req || !ul) return
    await nextTick()
    let target: HTMLElement | null = null
    for (const child of Array.from(ul.children)) {
      if ((child as HTMLElement).dataset.phKey === req.key) {
        target = child as HTMLElement
        break
      }
    }
    if (!target) return
    const delta = target.getBoundingClientRect().top - ul.getBoundingClientRect().top
    ul.scrollTo({ top: ul.scrollTop + delta, behavior: 'smooth' })
  },
)

/* ── drag & drop reordering ───────────────────────────────────────── */
// `dragKey` arms the native `draggable` attribute on a single row so that a
// drag can only start from the grip handle (keeps text selection / inputs usable).
const dragKey = ref<string | null>(null)
const dragIndex = ref<number | null>(null)
const overIndex = ref<number | null>(null)

function armDrag(key: string) {
  dragKey.value = key
}

function onHandleMouseUp() {
  // Click without dragging: disarm so the row isn't left draggable.
  if (dragIndex.value === null) dragKey.value = null
}

function onDragStart(idx: number, e: DragEvent) {
  dragIndex.value = idx
  overIndex.value = idx
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(idx)) // Firefox requires data
  }
}

function onDragOver(idx: number) {
  if (dragIndex.value === null) return
  overIndex.value = idx
}

function onDrop(idx: number) {
  const from = dragIndex.value
  if (from === null || from === idx) {
    resetDrag()
    return
  }
  const keys = session.placeholderList.map((p) => p.key)
  const [moved] = keys.splice(from, 1)
  keys.splice(idx, 0, moved)
  session.reorderPlaceholders(keys)
  resetDrag()
}

function resetDrag() {
  dragKey.value = null
  dragIndex.value = null
  overIndex.value = null
}

/* ── per-row rename state ─────────────────────────────────────────── */
const editingKey = ref<string | null>(null)
const editValue  = ref('')
const editError  = ref('')
const editInputEl = ref<HTMLInputElement | null>(null)
/** Briefly ignore row clicks right after dismissing a rename via outside-click. */
let suppressRowClickUntil = 0

// Function ref — only the single editing row renders this input (v-if), so it
// always points to the active field (a string ref inside v-for can be an array).
function setEditInputEl(el: unknown) {
  editInputEl.value = (el as HTMLInputElement | null) ?? null
}

async function startRename(key: string) {
  editingKey.value = key
  editValue.value  = key
  editError.value  = ''
  await nextTick()
  editInputEl.value?.focus()
  editInputEl.value?.select()
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

/* Clicking anywhere outside the active rename field discards the edit —
 * covers non-focusable targets (plain text / gaps) that never fire `blur`. */
function onDocMouseDown(e: MouseEvent) {
  if (!editingKey.value) return
  const target = e.target as Node | null
  if (editInputEl.value && target && editInputEl.value.contains(target)) return
  cancelRename()
  suppressRowClickUntil = Date.now() + 250
}

onMounted(() => document.addEventListener('mousedown', onDocMouseDown))
onUnmounted(() => document.removeEventListener('mousedown', onDocMouseDown))

/* ── row click → scroll the matching highlight into view ──────────── */
function onRowClick(key: string, e: MouseEvent) {
  if (Date.now() < suppressRowClickUntil) return
  if (editingKey.value) return
  const t = e.target as HTMLElement | null
  // Ignore clicks on dedicated controls (rename trigger/field, type toggle,
  // drag grip, remove button, sensitive value field).
  if (t && typeof t.closest === 'function' && t.closest('button, input, a')) return
  session.requestScrollToHighlight(key)
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

    <ul ref="listEl" class="space-y-1.5 max-h-56 overflow-y-auto pr-3">
      <li
        v-for="(ph, idx) in session.placeholderList"
        :key="ph.key"
        :data-ph-key="ph.key"
        :draggable="dragKey === ph.key"
        class="flex items-start gap-2 text-sm px-2 py-1.5 rounded bg-gray-800/40 transition-colors cursor-pointer"
        :class="{
          'opacity-40': dragIndex === idx,
          'ring-1 ring-blue-500/60': overIndex === idx && dragIndex !== null && dragIndex !== idx,
        }"
        @dragstart="onDragStart(idx, $event)"
        @dragover.prevent="onDragOver(idx)"
        @drop.prevent="onDrop(idx)"
        @dragend="resetDrag"
        @click="onRowClick(ph.key, $event)"
      >
        <!-- drag handle -->
        <button
          class="self-center flex-shrink-0 text-gray-600 hover:text-gray-300 cursor-grab active:cursor-grabbing"
          title="Drag to reorder"
          @mousedown="armDrag(ph.key)"
          @mouseup="onHandleMouseUp"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" fill="currentColor" class="w-3 h-3.5">
            <circle cx="5" cy="3" r="1.3" /><circle cx="11" cy="3" r="1.3" />
            <circle cx="5" cy="8" r="1.3" /><circle cx="11" cy="8" r="1.3" />
            <circle cx="5" cy="13" r="1.3" /><circle cx="11" cy="13" r="1.3" />
          </svg>
        </button>

        <!-- type toggle -->
        <button
          class="self-center w-4 h-4 rounded-full flex-shrink-0 flex items-center justify-center transition-colors"
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
            <div class="flex items-center gap-1">
              <input
                :ref="setEditInputEl"
                :value="editValue"
                class="flex-1 min-w-0 font-mono text-xs bg-gray-900 border rounded px-1.5 py-0.5 focus:outline-none focus:ring-1"
                :class="editError
                  ? 'border-red-500 text-red-300 focus:ring-red-500'
                  : 'border-gray-600 text-gray-200 focus:ring-blue-500'"
                @input="onEditInput(($event.target as HTMLInputElement).value)"
                @keydown="onKeydown"
                @blur="cancelRename"
              />
              <!-- Enter-to-confirm hint -->
              <span
                class="flex-shrink-0 flex items-center text-gray-500"
                title="Press Enter to confirm (Esc or click away to cancel)"
              >
                <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="9 10 4 15 9 20"/>
                  <path d="M20 4v7a4 4 0 0 1-4 4H4"/>
                </svg>
              </span>
            </div>
            <p v-if="editError" class="text-[10px] text-red-400 mt-0.5">{{ editError }}</p>
            <p v-else-if="editValue !== sanitizeKey(editValue)" class="text-[10px] text-gray-500 mt-0.5">
              Will save as: <span class="text-gray-300 font-mono">{{ sanitizeKey(editValue) }}</span>
            </p>
          </div>
          <button
            v-else
            class="font-mono text-xs text-left w-full truncate hover:underline decoration-dotted rounded px-1 -mx-1 py-0.5 bg-white/[0.03] hover:bg-white/[0.06] transition-colors"
            :class="ph.type === 'tailor' ? 'text-blue-400' : 'text-amber-400'"
            title="Click to rename"
            @click="startRename(ph.key)"
          >
            {{ ph.key }}
          </button>

          <!-- selected text preview (value of the highlight; still selectable) -->
          <p class="text-[11px] text-gray-500 truncate mt-0.5 cursor-text">{{ ph.selected_text }}</p>

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
