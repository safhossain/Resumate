<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { usePipelineStore } from '../stores/pipeline'
import type { ChangeLogEntry } from '../api/client'

const pipeline = usePipelineStore()
const activeTab = ref<'output' | 'changes'>('output')

/* ── resizable panel ──────────────────────────────────────────────── */
const MIN_HEIGHT = 56  // tall enough to show the header row only
const RESERVED_TOP = 80 // px to leave above the panel for DocumentViewer
const height = ref(288) // default ≈ old max-h-72
const panelEl = ref<HTMLDivElement | null>(null)

let dragStartY = 0
let dragStartHeight = 0

function maxHeight(): number {
  const parent = panelEl.value?.parentElement
  if (!parent) return Infinity
  return Math.max(MIN_HEIGHT, parent.clientHeight - RESERVED_TOP)
}

function onDragMove(e: MouseEvent) {
  const next = dragStartHeight + (dragStartY - e.clientY)
  height.value = Math.min(maxHeight(), Math.max(MIN_HEIGHT, next))
}

function onDragEnd() {
  document.removeEventListener('mousemove', onDragMove)
  document.removeEventListener('mouseup', onDragEnd)
  document.body.style.cursor = ''
  document.body.style.userSelect = ''
}

function startDrag(e: MouseEvent) {
  e.preventDefault()
  dragStartY = e.clientY
  dragStartHeight = height.value
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
  document.body.style.cursor = 'ns-resize'
  document.body.style.userSelect = 'none'
}

onUnmounted(onDragEnd)

/** Stages collapsed by default beyond the most recent one. */
const collapsed = ref<Record<number, boolean>>({})

const log = computed<ChangeLogEntry[]>(() => pipeline.latestOutput?.changes_log ?? [])

function isOpen(idx: number): boolean {
  // default-open the latest entry; everything else default-collapsed
  if (idx === log.value.length - 1) {
    return collapsed.value[idx] !== true
  }
  return collapsed.value[idx] === false
}

function toggle(idx: number) {
  collapsed.value = { ...collapsed.value, [idx]: isOpen(idx) }
}

function stageBadgeClass(stage: ChangeLogEntry['stage']): string {
  if (stage === 'initial') return 'bg-blue-900/40 text-blue-300 border-blue-800/60'
  if (stage === 'auto_retry') return 'bg-amber-900/40 text-amber-300 border-amber-800/60'
  return 'bg-purple-900/40 text-purple-300 border-purple-800/60'
}
</script>

<template>
  <div
    v-if="pipeline.latestOutput"
    ref="panelEl"
    class="relative border-t border-gray-800 bg-[#0d111c] flex-shrink-0 flex flex-col"
    :style="{ height: height + 'px' }"
  >
    <!-- drag handle (sibling of the scroll container, so it never scrolls away) -->
    <div
      class="absolute top-0 left-0 right-0 h-2.5 -translate-y-1/2 z-20 cursor-ns-resize group"
      title="Drag to resize"
      @mousedown="startDrag"
    >
      <div class="h-full w-full group-hover:bg-blue-500/40 transition-colors" />
    </div>

    <!-- scrollable content wrapper -->
    <div class="flex-1 min-h-0 overflow-y-auto">
    <!-- sticky header ------------------------------------------------ -->
    <div class="flex items-center justify-between px-5 py-2 border-b border-gray-800 bg-[#0d111c] sticky top-0 z-10">
      <div class="flex items-center gap-3">

        <!-- tabs -->
        <div class="flex gap-1">
          <button
            class="text-xs font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded transition-colors"
            :class="activeTab === 'output'
              ? 'bg-gray-700 text-gray-200'
              : 'text-gray-500 hover:text-gray-300'"
            @click="activeTab = 'output'"
          >
            Output
          </button>
          <button
            class="text-xs font-semibold uppercase tracking-wider px-2.5 py-0.5 rounded transition-colors"
            :class="activeTab === 'changes'
              ? 'bg-gray-700 text-gray-200'
              : 'text-gray-500 hover:text-gray-300'"
            @click="activeTab = 'changes'"
          >
            Changes Made
          </button>
        </div>

        <!-- page info badge -->
        <span
          v-if="pipeline.latestOutput.page_info"
          class="text-xs px-2 py-0.5 rounded-full"
          :class="pipeline.latestOutput.page_info.within_target
            ? 'bg-green-900/40 text-green-400'
            : 'bg-red-900/40 text-red-400'"
        >
          {{ pipeline.latestOutput.page_info.page_count }} page(s)
          <template v-if="pipeline.latestOutput.page_info.target_pages">
            / target {{ pipeline.latestOutput.page_info.target_pages }}
          </template>
        </span>

        <span
          v-if="pipeline.latestOutput.retry_number"
          class="text-[10px] text-gray-500"
        >
          retry #{{ pipeline.latestOutput.retry_number }}
        </span>
      </div>

      <div class="flex items-center gap-2">
        <!-- retry -->
        <button
          v-if="pipeline.latestOutput.can_retry"
          :disabled="pipeline.isRetrying"
          class="px-3 py-1 rounded text-xs font-medium bg-amber-600/20 text-amber-400 hover:bg-amber-600/40 transition-colors disabled:opacity-50"
          @click="pipeline.retry()"
        >
          <span v-if="pipeline.isRetrying">Retrying…</span>
          <span v-else>Retry (page limit)</span>
        </button>

        <!-- download -->
        <a
          :href="pipeline.latestOutput.download_url"
          download
          class="px-3 py-1 rounded text-xs font-medium bg-blue-600/20 text-blue-400 hover:bg-blue-600/40 transition-colors"
        >
          Download
        </a>
      </div>
    </div>

    <!-- tab content -------------------------------------------------- -->

    <!-- Output -->
    <div
      v-if="activeTab === 'output'"
      class="p-5 prose prose-invert prose-sm max-w-none"
      v-html="pipeline.latestOutput.preview_html"
    />

    <!-- Changes Made -->
    <div v-else class="p-5 space-y-2">
      <!-- multi-stage log -->
      <template v-if="log.length">
        <div
          v-for="(entry, idx) in log"
          :key="idx"
          class="rounded-lg border border-gray-800 bg-gray-900/60"
        >
          <button
            class="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-800/40 transition-colors rounded-t-lg"
            @click="toggle(idx)"
          >
            <span
              class="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded border"
              :class="stageBadgeClass(entry.stage)"
            >Stage {{ idx + 1 }}</span>
            <span class="text-sm text-gray-300 flex-1 truncate">{{ entry.label }}</span>
            <span
              v-if="entry.page_count != null && entry.target_pages != null"
              class="text-[10px] text-gray-500"
            >{{ entry.page_count }}p / target {{ entry.target_pages }}p</span>
            <span class="text-gray-600 text-xs select-none">{{ isOpen(idx) ? '▾' : '▸' }}</span>
          </button>
          <div
            v-if="isOpen(idx)"
            class="px-4 pb-3 pt-1 border-t border-gray-800/60"
          >
            <p
              v-if="entry.text"
              class="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap"
            >{{ entry.text }}</p>
            <p v-else class="text-xs text-gray-600 italic">(empty summary returned for this stage)</p>
          </div>
        </div>
      </template>

      <!-- legacy single-string fallback (older outputs without changes_log) -->
      <template v-else-if="pipeline.latestOutput.changes_made">
        <p class="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">{{ pipeline.latestOutput.changes_made }}</p>
      </template>

      <p v-else class="text-sm text-gray-500 italic">No changes summary returned.</p>
    </div>
    </div>
  </div>
</template>
