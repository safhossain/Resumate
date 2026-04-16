<script setup lang="ts">
import { ref, watch, nextTick, computed, onMounted, onUnmounted } from 'vue'
import { useSessionStore } from '../stores/session'
import type { PlaceholderResponse } from '../api/client'

const session = useSessionStore()

const viewerEl = ref<HTMLDivElement | null>(null)
const contentEl = ref<HTMLDivElement | null>(null)
const popoverEl = ref<HTMLDivElement | null>(null)
const popover = ref<{
  x: number
  y: number
  text: string
  startOffset: number
  endOffset: number
} | null>(null)

/* ── dismiss popover on outside click ───────────────────────────── */

function onDocumentMouseDown(e: MouseEvent) {
  if (!popover.value) return
  const target = e.target as HTMLElement
  if (popoverEl.value?.contains(target)) return
  closePopover()
}

onMounted(() => document.addEventListener('mousedown', onDocumentMouseDown))
onUnmounted(() => document.removeEventListener('mousedown', onDocumentMouseDown))

/* ── selection → offset mapping ─────────────────────────────────── */

function findOffsetAncestor(node: Node): HTMLElement | null {
  let el: HTMLElement | null = node instanceof HTMLElement ? node : node.parentElement
  while (el && el !== viewerEl.value) {
    if (el.hasAttribute('data-offset')) return el
    el = el.parentElement
  }
  return null
}

function charOffsetInElement(element: HTMLElement, targetNode: Node, targetOffset: number): number {
  const r = document.createRange()
  r.selectNodeContents(element)
  r.setEnd(targetNode, targetOffset)
  return r.toString().length
}

function getSelectionInfo(): { text: string; start: number; end: number } | null {
  const sel = window.getSelection()
  if (!sel || sel.isCollapsed || !sel.rangeCount) return null

  const range = sel.getRangeAt(0)
  const text = sel.toString()
  if (!text.trim()) return null

  const startEl = findOffsetAncestor(range.startContainer)
  const endEl = findOffsetAncestor(range.endContainer)
  if (!startEl || !endEl) return null

  const startElOffset = parseInt(startEl.dataset.offset!, 10)
  const endElOffset = parseInt(endEl.dataset.offset!, 10)

  const startLocal = charOffsetInElement(startEl, range.startContainer, range.startOffset)
  const endLocal = charOffsetInElement(endEl, range.endContainer, range.endOffset)

  return {
    text,
    start: startElOffset + startLocal,
    end: endElOffset + endLocal,
  }
}

/* ── popover on text selection ──────────────────────────────────── */

function onMouseUp() {
  setTimeout(() => {
    const info = getSelectionInfo()
    if (!info || !viewerEl.value) {
      return
    }

    const sel = window.getSelection()
    if (!sel || !sel.rangeCount) return
    const range = sel.getRangeAt(0)
    const rects = range.getClientRects()
    if (!rects.length) return

    const last = rects[rects.length - 1]
    const container = viewerEl.value.getBoundingClientRect()

    popover.value = {
      x: last.right - container.left,
      y: last.bottom - container.top + viewerEl.value.scrollTop + 4,
      text: info.text,
      startOffset: info.start,
      endOffset: info.end,
    }
  }, 10)
}

function closePopover() {
  popover.value = null
  window.getSelection()?.removeAllRanges()
}

async function markAs(type: 'tailor' | 'sensitive') {
  if (!popover.value) return
  try {
    await session.addPlaceholder(
      popover.value.text,
      popover.value.startOffset,
      popover.value.endOffset,
      type,
    )
  } catch (e) {
    console.error('Failed to add placeholder:', e)
  }
  closePopover()
}

/* ── highlight injection ────────────────────────────────────────── */

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function textToInnerHtml(s: string): string {
  let h = escapeHtml(s)
  h = h.replace(/\t/g, '<span class="docx-tab">\t</span>')
  h = h.replace(/\n/g, '<br>')
  return h
}

function buildHighlightedContent(
  elementText: string,
  elementOffset: number,
  phs: PlaceholderResponse[],
): string {
  const overlapping = phs
    .filter(
      (ph) =>
        ph.start_offset < elementOffset + elementText.length &&
        ph.end_offset > elementOffset,
    )
    .sort((a, b) => a.start_offset - b.start_offset)

  if (!overlapping.length) return textToInnerHtml(elementText) || '&nbsp;'

  let result = ''
  let pos = 0

  for (const ph of overlapping) {
    const localStart = Math.max(0, ph.start_offset - elementOffset)
    const localEnd = Math.min(elementText.length, ph.end_offset - elementOffset)

    if (localStart > pos) {
      result += textToInnerHtml(elementText.slice(pos, localStart))
    }

    const cls = ph.type === 'tailor' ? 'placeholder-tailor-inline' : 'placeholder-sensitive-inline'
    result += `<span class="${cls}" data-ph-key="${escapeHtml(ph.key)}">`
    result += textToInnerHtml(elementText.slice(localStart, localEnd))
    result += '</span>'

    pos = localEnd
  }

  if (pos < elementText.length) {
    result += textToInnerHtml(elementText.slice(pos))
  }

  return result || '&nbsp;'
}

function applyHighlights() {
  if (!contentEl.value) return
  const els = contentEl.value.querySelectorAll<HTMLElement>('[data-offset]')
  const phList = Object.values(session.placeholders)

  els.forEach((el) => {
    const elOffset = parseInt(el.dataset.offset!, 10)
    const elemId = el.dataset.elementId
    const structElem = session.documentStructure.find((e) => e.id === elemId)
    if (!structElem) return

    el.innerHTML = buildHighlightedContent(structElem.text, elOffset, phList)
  })
}

watch(
  () => [session.renderedHtml, session.placeholders],
  async () => {
    await nextTick()
    applyHighlights()
  },
  { deep: true },
)

/* ── check if selection overlaps an existing placeholder ────────── */

const overlappingKey = computed(() => {
  if (!popover.value) return null
  for (const ph of Object.values(session.placeholders)) {
    if (
      ph.start_offset < popover.value.endOffset &&
      ph.end_offset > popover.value.startOffset
    ) {
      return ph.key
    }
  }
  return null
})
</script>

<template>
  <div class="relative overflow-auto bg-gray-900" ref="viewerEl" @mouseup="onMouseUp">
    <!-- empty state -->
    <div
      v-if="!session.hasSession"
      class="flex items-center justify-center h-full text-gray-600 text-sm select-none"
    >
      Upload a document to get started
    </div>

    <!-- tex: source + PDF side-by-side -->
    <div v-else-if="session.fileFormat === 'tex' && session.texPdfUrl" class="flex flex-col h-full">
      <div class="flex-1 min-h-0 flex">
        <div
          ref="contentEl"
          class="w-1/2 overflow-auto p-4 border-r border-gray-800 cursor-text"
          v-html="session.renderedHtml"
        />
        <iframe :src="session.texPdfUrl" class="w-1/2 bg-white" />
      </div>
    </div>

    <!-- docx / txt / tex-source-only -->
    <div v-else class="flex">
      <div
        ref="contentEl"
        class="flex-1 p-6 max-w-3xl mx-auto leading-relaxed cursor-text"
        v-html="session.renderedHtml"
      />

      <!-- info box -->
      <div class="w-56 flex-shrink-0 p-4 border-l border-gray-800">
        <div class="rounded-lg bg-gray-800/50 border border-gray-700/50 p-3">
          <p class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">How to use</p>
          <ol class="text-[11px] text-gray-500 space-y-1.5 list-decimal list-inside leading-relaxed">
            <li><span class="text-blue-400">Highlight</span> text to mark as a <b class="text-blue-400">tailor</b> (LLM rewrites) or <b class="text-amber-400">sensitive</b> (local-only) placeholder.</li>
            <li>Paste the <b class="text-gray-300">job posting</b> in the left panel.</li>
            <li>Pick model &amp; settings in the top bar.</li>
            <li>Hit <b class="text-gray-300">Tailor Resume</b>.</li>
          </ol>
          <p
            class="mt-2.5 pt-2 border-t border-gray-700/50 flex gap-2 text-[10px] text-gray-500 leading-relaxed"
            role="note"
          >
            <span
              class="flex-shrink-0 w-4 h-4 rounded-full border border-gray-600 text-gray-400 flex items-center justify-center text-[9px] font-semibold font-sans"
              aria-label="Additional tip"
            >i</span>
            <span>In <b class="text-gray-400">Placeholders</b>, click the colored dot to switch between <b class="text-blue-400">tailor</b> and <b class="text-amber-400">sensitive</b>.</span>
          </p>
          <p
            class="mt-2.5 pt-2 border-t border-gray-700/50 flex gap-2 text-[10px] text-gray-500 leading-relaxed"
            role="note"
          >
            <span
              class="flex-shrink-0 w-4 h-4 rounded-full border border-gray-600 text-gray-400 flex items-center justify-center text-[9px] font-semibold font-sans"
              aria-label="Sensitive value tip"
            >i</span>
            <span><b class="text-amber-400">Sensitive</b> rows show your <b class="text-gray-400">highlight</b> above and a <b class="text-gray-400">text field</b> below. That field is the value stitched into the output (not sent to the LLM). It starts as a copy of the highlight. Change it if the resume shows a placeholder or you want different wording in the final file.</span>
          </p>
        </div>
      </div>
    </div>

    <!-- popover -->
    <div
      v-if="popover"
      ref="popoverEl"
      class="absolute z-50 bg-gray-800 border border-gray-700 rounded-lg shadow-xl p-1.5 flex gap-1"
      :style="{
        left: popover.x + 'px',
        top: popover.y + 'px',
        transform: 'translateX(-50%)',
      }"
    >
      <button
        class="px-2.5 py-1 rounded text-xs font-medium bg-blue-600/20 text-blue-400 hover:bg-blue-600/40 transition-colors"
        @click="markAs('tailor')"
      >
        Tailor
      </button>
      <button
        class="px-2.5 py-1 rounded text-xs font-medium bg-amber-600/20 text-amber-400 hover:bg-amber-600/40 transition-colors"
        @click="markAs('sensitive')"
      >
        Sensitive
      </button>
      <button
        v-if="overlappingKey"
        class="px-2.5 py-1 rounded text-xs font-medium bg-red-600/20 text-red-400 hover:bg-red-600/40 transition-colors"
        @click="session.removePlaceholder(overlappingKey!); closePopover()"
      >
        Clear
      </button>
      <button
        class="px-2.5 py-1 rounded text-xs text-gray-500 hover:text-gray-300 transition-colors"
        @click="closePopover"
      >
        ✕
      </button>
    </div>
  </div>
</template>
