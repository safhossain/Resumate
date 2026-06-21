<script setup lang="ts">
import { ref, watch, nextTick, computed, onMounted, onUnmounted } from 'vue'
import { useSessionStore } from '../stores/session'
import { usePipelineStore } from '../stores/pipeline'
import { sanitizeKey } from '../stores/session'
import type { PlaceholderResponse } from '../api/client'

const session = useSessionStore()
const pipeline = usePipelineStore()

const viewerEl = ref<HTMLDivElement | null>(null)
const contentEl = ref<HTMLDivElement | null>(null)
const popoverEl = ref<HTMLDivElement | null>(null)
const nameInputEl = ref<HTMLInputElement | null>(null)
const popover = ref<{
  x: number
  y: number
  text: string
  startOffset: number
  endOffset: number
  /** Set after user picks a type when Quick label is enabled */
  pendingType?: 'tailor' | 'sensitive'
} | null>(null)

/* ── hover tooltip over an existing placeholder ─────────────────── */
const hoverTip = ref<{ x: number; y: number; type: 'tailor' | 'sensitive'; key: string } | null>(null)

/* ── right-click context menu over an existing placeholder ──────── */
const ctxMenuEl = ref<HTMLDivElement | null>(null)
const ctxMenu = ref<{ x: number; y: number; type: 'tailor' | 'sensitive'; key: string } | null>(null)

/** The name being typed in the quick-label input */
const quickLabelName = ref('')

/** True when the sanitized typed name already belongs to another placeholder */
const quickLabelDuplicate = computed(() => {
  const raw = quickLabelName.value.trim()
  if (!raw) return false
  return sanitizeKey(raw) in session.placeholders
})

/* ── ephemeral toasts ────────────────────────────────────────────── */
const toast = ref<{ text: string; kind: 'error' | 'warning' } | null>(null)
let toastTimer: ReturnType<typeof setTimeout> | null = null
function showToast(message: string, kind: 'error' | 'warning' = 'error', ms = 5500) {
  toast.value = { text: message, kind }
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = null }, ms)
}

/* ── dismiss popover on outside click ───────────────────────────── */

function onDocumentMouseDown(e: MouseEvent) {
  const target = e.target as HTMLElement

  // Dismiss the right-click menu on any click outside it.
  if (ctxMenu.value && !ctxMenuEl.value?.contains(target)) {
    ctxMenu.value = null
  }

  if (!popover.value) return
  if (popoverEl.value?.contains(target)) return

  // In naming phase, clicking outside creates with auto-name (or typed name if any).
  // If the typed name is a duplicate, discard the placeholder entirely.
  if (popover.value.pendingType) {
    if (quickLabelDuplicate.value) {
      closePopover()
      return
    }
    doCreatePlaceholder(
      popover.value.pendingType,
      quickLabelName.value.trim() ? sanitizeKey(quickLabelName.value) : undefined,
    )
    return
  }

  closePopover()
}

function onDocumentKeyDown(e: KeyboardEvent) {
  if (e.key === 'Escape' && ctxMenu.value) {
    ctxMenu.value = null
    return
  }
  if (!popover.value) return
  // Phase 1: Enter defaults to 'tailor'
  if (e.key === 'Enter' && !popover.value.pendingType) {
    e.preventDefault()
    markAs('tailor')
  }
}

onMounted(() => {
  document.addEventListener('mousedown', onDocumentMouseDown)
  document.addEventListener('keydown', onDocumentKeyDown)
})
onUnmounted(() => {
  document.removeEventListener('mousedown', onDocumentMouseDown)
  document.removeEventListener('keydown', onDocumentKeyDown)
})

/* ── selection → offset mapping ─────────────────────────────────── */

function findOffsetAncestor(node: Node): HTMLElement | null {
  let el: HTMLElement | null = node instanceof HTMLElement ? node : node.parentElement
  while (el && el !== viewerEl.value) {
    if (el.hasAttribute('data-offset')) return el
    el = el.parentElement
  }
  return null
}

/**
 * Compute the character offset within `element` that corresponds to a DOM
 * (node, offset) pair, treating <br> as a single "\n" character.
 *
 * Range.toString() does NOT include line breaks for <br>, but our raw_text
 * does (one "\n" per soft line break inside a paragraph). So we cannot use
 * Range.toString().length here — it would be off by 1 per <br> traversed.
 */
function charOffsetInElement(element: HTMLElement, targetNode: Node, targetOffset: number): number {
  // Length contribution of an entire subtree (text + <br>=1).
  function subtreeLength(node: Node): number {
    if (node.nodeType === Node.TEXT_NODE) return (node.textContent || '').length
    if (node.nodeName === 'BR') return 1
    let total = 0
    for (let i = 0; i < node.childNodes.length; i++) {
      total += subtreeLength(node.childNodes[i])
    }
    return total
  }

  let count = 0
  let done = false

  function walk(node: Node): void {
    if (done) return

    if (node === targetNode) {
      if (node.nodeType === Node.TEXT_NODE) {
        count += targetOffset
      } else {
        // Element node: targetOffset is the index of its child boundaries.
        for (let i = 0; i < targetOffset; i++) {
          count += subtreeLength(node.childNodes[i])
        }
      }
      done = true
      return
    }

    if (node.nodeType === Node.TEXT_NODE) {
      count += (node.textContent || '').length
      return
    }
    if (node.nodeName === 'BR') {
      count += 1
      return
    }

    for (let i = 0; i < node.childNodes.length; i++) {
      walk(node.childNodes[i])
      if (done) return
    }
  }

  walk(element)
  return count
}

function getSelectionInfo(): { text: string; start: number; end: number } | null {
  const sel = window.getSelection()
  if (!sel || sel.isCollapsed || !sel.rangeCount) return null

  const range = sel.getRangeAt(0)
  if (!sel.toString().trim()) return null

  const startEl = findOffsetAncestor(range.startContainer)
  const endEl = findOffsetAncestor(range.endContainer)
  if (!startEl || !endEl) return null

  const startElOffset = parseInt(startEl.dataset.offset!, 10)
  const endElOffset = parseInt(endEl.dataset.offset!, 10)

  const startLocal = charOffsetInElement(startEl, range.startContainer, range.startOffset)
  const endLocal = charOffsetInElement(endEl, range.endContainer, range.endOffset)

  const start = startElOffset + startLocal
  const end = endElOffset + endLocal
  if (end <= start) return null

  // Derive text from raw_text so it always matches the offsets exactly
  // (incl. \t and \n characters, which DOM Selection may normalise).
  const text = session.rawText.slice(start, end)
  if (!text) return null

  return { text, start, end }
}

/* ── popover on text selection ──────────────────────────────────── */

function onMouseUp() {
  setTimeout(async () => {
    const info = getSelectionInfo()
    if (!info || !viewerEl.value) {
      return
    }

    // If the selection overlaps an already-marked placeholder, do nothing:
    // re-marking it would 409, and clearing now lives in the right-click menu.
    const overlaps = Object.values(session.placeholders).some(
      (ph) => ph.start_offset < info.end && ph.end_offset > info.start,
    )
    if (overlaps) {
      window.getSelection()?.removeAllRanges()
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

    // After the popover renders, ensure it is fully visible inside the scroll container.
    await nextTick()
    if (popoverEl.value && viewerEl.value) {
      const popRect = popoverEl.value.getBoundingClientRect()
      const viewRect = viewerEl.value.getBoundingClientRect()
      if (popRect.bottom > viewRect.bottom) {
        viewerEl.value.scrollTop += popRect.bottom - viewRect.bottom + 8
      }
    }
  }, 10)
}

function closePopover() {
  popover.value = null
  window.getSelection()?.removeAllRanges()
}

/* ── hover / right-click on existing placeholder spans ──────────── */

function findPhSpan(target: EventTarget | null): HTMLElement | null {
  const el = target as HTMLElement | null
  if (!el || typeof el.closest !== 'function') return null
  return el.closest<HTMLElement>(
    '.placeholder-tailor-inline, .placeholder-sensitive-inline',
  )
}

function phInfoFromSpan(
  span: HTMLElement,
): { key: string; type: 'tailor' | 'sensitive' } | null {
  const key = span.dataset.phKey
  if (!key) return null
  const ph = session.placeholders[key]
  const type: 'tailor' | 'sensitive' =
    (ph?.type as 'tailor' | 'sensitive') ??
    (span.classList.contains('placeholder-sensitive-inline') ? 'sensitive' : 'tailor')
  return { key, type }
}

function onViewerMouseOver(e: MouseEvent) {
  if (ctxMenu.value) return
  const span = findPhSpan(e.target)
  if (!span || !viewerEl.value) {
    hoverTip.value = null
    return
  }
  const info = phInfoFromSpan(span)
  if (!info) {
    hoverTip.value = null
    return
  }
  const r = span.getBoundingClientRect()
  const c = viewerEl.value.getBoundingClientRect()
  hoverTip.value = {
    x: r.left - c.left + viewerEl.value.scrollLeft + r.width / 2,
    y: r.top - c.top + viewerEl.value.scrollTop,
    type: info.type,
    key: info.key,
  }
}

function onViewerMouseLeave() {
  hoverTip.value = null
}

function onViewerClick(e: MouseEvent) {
  // Left-click on an existing highlight: ask the placeholder list to scroll
  // the associated box into view. Ignore clicks that are part of a text
  // selection (handled by onMouseUp).
  if (e.button !== 0) return
  const sel = window.getSelection()
  if (sel && !sel.isCollapsed) return
  const span = findPhSpan(e.target)
  if (!span) return
  const key = span.dataset.phKey
  if (key) session.requestScrollToPlaceholder(key)
}

function onViewerContextMenu(e: MouseEvent) {
  const span = findPhSpan(e.target)
  if (!span || !viewerEl.value) return // allow the native menu elsewhere
  e.preventDefault()
  const info = phInfoFromSpan(span)
  if (!info) return
  hoverTip.value = null
  const c = viewerEl.value.getBoundingClientRect()
  ctxMenu.value = {
    x: e.clientX - c.left + viewerEl.value.scrollLeft,
    y: e.clientY - c.top + viewerEl.value.scrollTop,
    type: info.type,
    key: info.key,
  }
}

async function deletePlaceholderFromMenu() {
  const key = ctxMenu.value?.key
  ctxMenu.value = null
  if (!key) return
  await session.removePlaceholder(key)
}

async function markAs(type: 'tailor' | 'sensitive') {
  if (!popover.value) return

  if (pipeline.quickLabel) {
    // Enter naming phase: show text input inside the popover
    popover.value = { ...popover.value, pendingType: type }
    quickLabelName.value = ''
    await nextTick()
    nameInputEl.value?.focus()
    return
  }

  await doCreatePlaceholder(type, undefined)
}

async function confirmQuickLabel() {
  if (!popover.value?.pendingType) return
  if (quickLabelDuplicate.value) return   // block enter on duplicate
  const raw = quickLabelName.value.trim()
  const customKey = raw ? sanitizeKey(raw) : undefined
  await doCreatePlaceholder(popover.value.pendingType, customKey || undefined)
}

async function doCreatePlaceholder(type: 'tailor' | 'sensitive', customKey?: string) {
  if (!popover.value) return
  try {
    const result = await session.addPlaceholder(
      popover.value.text,
      popover.value.startOffset,
      popover.value.endOffset,
      type,
      customKey,
    )
    closePopover()
    if (result?.warning) {
      showToast(result.warning, 'warning', 8000)
    }
  } catch (e) {
    console.error('Failed to add placeholder:', e)
    const raw = e instanceof Error ? e.message : String(e)
    const friendly =
      /400/.test(raw)
        ? "This selection couldn't be mapped back to the document — likely a tab, soft line break, or other formatting edge case we don't yet support. Try selecting a slightly different region. (We're working on covering more cases.)"
        : `Couldn't add placeholder: ${raw}`
    showToast(friendly, 'error')
    closePopover()
  }
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

</script>

<template>
  <div class="flex h-full bg-gray-900">
    <!-- rendered resume — independent vertical scroll -->
    <div
      class="relative flex-1 min-w-0 overflow-auto"
      ref="viewerEl"
      @mouseup="onMouseUp"
      @click="onViewerClick"
      @mouseover="onViewerMouseOver"
      @mouseleave="onViewerMouseLeave"
      @contextmenu="onViewerContextMenu"
    >
    <!-- empty state -->
    <div
      v-if="!session.hasSession"
      class="flex items-center justify-center h-full text-gray-600 text-sm select-none"
    >
      Upload a document to get started
    </div>

    <!-- docx / txt / tex -->
    <div
      v-else
      ref="contentEl"
      class="p-6 pb-16 max-w-3xl mx-auto leading-relaxed cursor-text"
      v-html="session.renderedHtml"
    />

    <!-- transient toast (error = red, warning = amber) -->
    <div
      v-if="toast"
      class="absolute top-3 right-3 z-50 max-w-sm rounded-lg backdrop-blur px-3 py-2 shadow-lg flex items-start gap-2"
      :class="toast.kind === 'warning'
        ? 'border border-amber-700/60 bg-amber-950/90'
        : 'border border-red-800/60 bg-red-950/90'"
      role="alert"
    >
      <span
        class="flex-shrink-0 w-4 h-4 rounded-full border flex items-center justify-center text-[9px] font-semibold font-sans mt-0.5"
        :class="toast.kind === 'warning'
          ? 'border-amber-500/60 text-amber-300'
          : 'border-red-400/60 text-red-300'"
        aria-hidden="true"
      >!</span>
      <p
        class="text-[11px] leading-relaxed flex-1"
        :class="toast.kind === 'warning' ? 'text-amber-200' : 'text-red-200'"
      >{{ toast.text }}</p>
      <button
        class="text-xs flex-shrink-0 leading-none"
        :class="toast.kind === 'warning' ? 'text-amber-400 hover:text-amber-200' : 'text-red-400 hover:text-red-200'"
        title="Dismiss"
        @click="toast = null"
      >✕</button>
    </div>

    <!-- popover -->
    <div
      v-if="popover"
      ref="popoverEl"
      class="absolute z-50 bg-gray-800 border border-gray-700 rounded-lg shadow-xl p-1.5 flex gap-1 items-center"
      :style="{
        left: popover.x + 'px',
        top: popover.y + 'px',
        transform: 'translateX(-50%)',
      }"
    >
      <!-- phase 1: type selection -->
      <template v-if="!popover.pendingType">
        <button
          class="px-2.5 py-1 rounded text-xs font-medium bg-amber-600/20 text-amber-400 hover:bg-amber-600/40 transition-colors"
          @click="markAs('sensitive')"
        >
          Sensitive
        </button>
        <button
          class="px-2.5 py-1 rounded text-xs font-medium bg-blue-600/20 text-blue-400 hover:bg-blue-600/40 transition-colors"
          @click="markAs('tailor')"
        >
          Tailor
        </button>
        <button
          class="flex items-center justify-center text-gray-500 hover:text-blue-400 transition-colors px-1"
          title="Press Enter to mark as Tailor"
          @click="markAs('tailor')"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 10 4 15 9 20"/>
            <path d="M20 4v7a4 4 0 0 1-4 4H4"/>
          </svg>
        </button>
        <button
          class="px-2.5 py-1 rounded text-xs text-gray-500 hover:text-gray-300 transition-colors"
          @click="closePopover"
        >
          ✕
        </button>
      </template>

      <!-- phase 2: quick label naming -->
      <template v-else>
        <!-- type badge -->
        <span
          :class="popover.pendingType === 'tailor'
            ? 'text-blue-400 bg-blue-600/20 border-blue-700/50'
            : 'text-amber-400 bg-amber-600/20 border-amber-700/50'"
          class="px-2 py-0.5 rounded text-[10px] font-semibold border select-none capitalize"
        >{{ popover.pendingType }}</span>

        <!-- name input + duplicate error -->
        <div class="flex flex-col gap-0.5">
          <input
            ref="nameInputEl"
            v-model="quickLabelName"
            type="text"
            placeholder="placeholder name…"
            class="w-40 bg-gray-700 border rounded px-2 py-0.5 text-xs placeholder-gray-500 focus:outline-none focus:ring-1 transition-colors"
            :class="quickLabelDuplicate
              ? 'border-red-500/70 text-red-300 bg-red-950/40 focus:ring-red-500'
              : 'border-gray-600 text-gray-100 focus:ring-blue-500'"
            @keydown.enter.prevent="confirmQuickLabel"
            @keydown.esc.prevent="closePopover"
          />
          <p
            v-if="quickLabelDuplicate"
            class="text-[10px] text-red-400 leading-tight px-0.5"
          >Name already exists.</p>
        </div>

        <!-- enter hint -->
        <span
          class="flex items-center gap-0.5 text-gray-500 select-none"
          title="Press Enter to confirm, or click away to use auto-name"
        >
          <svg xmlns="http://www.w3.org/2000/svg" class="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 10 4 15 9 20"/>
            <path d="M20 4v7a4 4 0 0 1-4 4H4"/>
          </svg>
        </span>

        <button
          class="px-2.5 py-1 rounded text-xs text-gray-500 hover:text-gray-300 transition-colors"
          @click="closePopover"
        >
          ✕
        </button>
      </template>
    </div>

    <!-- hover tooltip over an existing placeholder -->
    <div
      v-if="hoverTip"
      class="absolute z-40 pointer-events-none flex items-center gap-1.5 px-2 py-1 rounded-md bg-gray-900 border border-gray-700 shadow-lg whitespace-nowrap"
      :style="{
        left: hoverTip.x + 'px',
        top: hoverTip.y + 'px',
        transform: 'translate(-50%, calc(-100% - 6px))',
      }"
    >
      <span
        class="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide select-none"
        :class="hoverTip.type === 'tailor'
          ? 'bg-blue-600/25 text-blue-300'
          : 'bg-amber-600/25 text-amber-300'"
      >{{ hoverTip.type }}</span>
      <span class="text-[11px] font-mono text-gray-300">{{ hoverTip.key }}</span>
    </div>

    <!-- right-click menu: delete an existing placeholder -->
    <div
      v-if="ctxMenu"
      ref="ctxMenuEl"
      class="absolute z-50 bg-gray-800 border border-gray-700 rounded-lg shadow-xl overflow-hidden min-w-[11rem]"
      :style="{ left: ctxMenu.x + 'px', top: ctxMenu.y + 'px' }"
    >
      <div class="flex items-center gap-1.5 px-3 py-1.5 border-b border-gray-700/70">
        <span
          class="px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide select-none"
          :class="ctxMenu.type === 'tailor'
            ? 'bg-blue-600/25 text-blue-300'
            : 'bg-amber-600/25 text-amber-300'"
        >{{ ctxMenu.type }}</span>
        <span class="text-[11px] font-mono text-gray-300 truncate">{{ ctxMenu.key }}</span>
      </div>
      <button
        class="w-full flex items-center gap-2 px-3 py-1.5 text-left text-xs text-red-400 hover:bg-red-600/20 transition-colors"
        @click="deletePlaceholderFromMenu"
      >
        <span class="text-sm leading-none">✕</span>
        Delete placeholder
      </button>
    </div>
    </div>

    <!-- how-to-use sidebar — independent vertical scroll -->
    <div
      v-if="session.hasSession"
      class="w-56 flex-shrink-0 overflow-y-auto border-l border-gray-800 p-4"
    >
      <div class="rounded-lg bg-gray-800/50 border border-gray-700/50 p-3">
        <p class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider mb-2">How to use</p>
        <ol class="text-[11px] text-gray-500 space-y-1.5 list-decimal list-inside leading-relaxed">
          <li><span class="text-blue-400">Highlight</span> text to mark as a <b class="text-blue-400">tailor</b> (LLM rewrites) or <b class="text-amber-400">sensitive</b> (local-only) placeholder.</li>
          <li>Paste the <b class="text-gray-300">job posting</b> in the left panel.</li>
          <li>Pick model &amp; settings in the top bar.</li>
          <li><b class="text-gray-400">Faux</b> (top bar): when on, the LLM may add plausible skills or experience that fit your profile and the job; when off, it only rewrites using facts already in your resume and ACC.</li>
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
          <span><b class="text-amber-400">Sensitive</b> rows show your <b class="text-gray-400">highlight</b> above and a <b class="text-gray-400">text field</b> below. That field is the value stitched into the output (not sent to the LLM). It starts as a copy of the highlight. Change it if the resume shows a placeholder, or if you want different wording in the final file.</span>
        </p>
        <p
          class="mt-2.5 pt-2 border-t border-gray-700/50 flex gap-2 text-[10px] text-gray-500 leading-relaxed"
          role="note"
        >
          <span
            class="flex-shrink-0 w-4 h-4 rounded-full border border-gray-600 text-gray-400 flex items-center justify-center text-[9px] font-semibold font-sans"
            aria-label="Placeholder naming tip"
          >i</span>
          <span><b class="text-gray-400">Auto-naming</b> picks a short key from what you highlighted (simple values like email/phone get obvious names; longer text uses the most salient words). Keys are always <b class="text-gray-400">lowercase</b> with <b class="text-gray-400">underscores only</b>, spaces and hyphens become underscores. <b class="text-gray-400">Rename</b> anytime: in <b class="text-gray-400">Placeholders</b>, click a key name, edit, then press Enter or click away to save.</span>
        </p>
        <p
          class="mt-2.5 pt-2 border-t border-amber-900/40 flex gap-2 text-[10px] text-amber-700/80 leading-relaxed"
          role="note"
        >
          <span
            class="flex-shrink-0 w-4 h-4 rounded-full border border-amber-700/60 text-amber-500 flex items-center justify-center text-[9px] font-semibold font-sans"
            aria-label="Auto-naming caution"
          >!</span>
          <span><b class="text-amber-500">Caution with auto-naming:</b> for long lists, the key may name one item rather than the whole (e.g. <b class="text-amber-400/80">vue</b> for a 9-library list). The LLM reads both the key and the full value, but a descriptive name like <b class="text-amber-400/80">tech_stack</b> or <b class="text-amber-400/80">frameworks_list</b> produces more reliable edits. Rename list-type placeholders manually.</span>
        </p>
        <p
          class="mt-2.5 pt-2 border-t border-gray-700/50 flex gap-2 text-[10px] text-gray-500 leading-relaxed"
          role="note"
        >
          <span
            class="flex-shrink-0 w-4 h-4 rounded-full border border-gray-600 text-gray-400 flex items-center justify-center text-[9px] font-semibold font-sans"
            aria-label="Quick label tip"
          >i</span>
          <span><b class="text-gray-400">Quick label</b> (top bar toggle, on by default) lets you type a custom name right after marking a selection. Press <b class="text-gray-400">Enter</b> to confirm, or click away to fall back to the auto-generated name. Turn it off to skip the naming step entirely.</span>
        </p>
        <p
          v-if="session.fileFormat === 'tex'"
          class="mt-2.5 pt-2 border-t border-amber-900/40 flex gap-2 text-[10px] text-amber-700/80 leading-relaxed"
          role="note"
        >
          <span
            class="flex-shrink-0 w-4 h-4 rounded-full border border-amber-700/60 text-amber-500 flex items-center justify-center text-[9px] font-semibold font-sans"
            aria-label="LaTeX caution"
          >!</span>
          <span><b class="text-amber-500">.tex files:</b> avoid selecting text that starts or ends mid-brace (e.g. selecting only part of <b class="text-amber-400/80">\textbf{word}</b>). Imbalanced <b class="text-amber-400/80">{ }</b> in a placeholder value can break LaTeX compilation. An amber warning appears if a selection looks risky.</span>
        </p>
      </div>
    </div>
  </div>
</template>
