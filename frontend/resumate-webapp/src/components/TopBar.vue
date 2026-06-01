<script setup lang="ts">
import { computed } from 'vue'
import { usePipelineStore } from '../stores/pipeline'
import { useSessionStore } from '../stores/session'

const pipeline = usePipelineStore()
const session = useSessionStore()

const moddegOptions = [
  { value: 'low', label: 'Low' },
  { value: 'medium-low', label: 'Med-Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'medium-high', label: 'Med-High' },
  { value: 'high', label: 'High' },
]

const canTailor = computed(
  () => session.hasSession && session.placeholderList.length > 0 && pipeline.jobPosting.trim().length > 0,
)

const disabledReason = computed(() => {
  if (pipeline.isTailoring) return 'Tailoring in progress…'
  const missing: string[] = []
  if (!session.hasSession) missing.push('upload a resume')
  if (!session.placeholderList.length) missing.push('add at least one placeholder')
  if (!pipeline.jobPosting.trim()) missing.push('paste a job posting')
  if (!missing.length) return ''
  return 'To tailor: ' + missing.join(', and ') + '.'
})
</script>

<template>
  <header class="flex items-center gap-4 px-5 py-2.5 bg-gray-900 border-b border-gray-800 flex-shrink-0">
    <span class="text-lg font-bold tracking-tight text-blue-400 mr-4 select-none">Resumate</span>

    <!-- model -->
    <label class="flex items-center gap-1.5 text-xs text-gray-400">
      Model
      <select
        v-model="pipeline.model"
        class="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        <option v-for="m in pipeline.models" :key="m" :value="m">{{ m }}</option>
      </select>
    </label>

    <!-- moddeg -->
    <label class="flex items-center gap-1.5 text-xs text-gray-400">
      Mod&nbsp;Deg
      <select
        v-model="pipeline.moddeg"
        class="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
      >
        <option v-for="o in moddegOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
      </select>
    </label>

    <!-- faux -->
    <label class="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer select-none">
      <input
        v-model="pipeline.faux"
        type="checkbox"
        class="accent-blue-500 w-3.5 h-3.5"
      />
      Faux
    </label>

    <!-- quick label -->
    <label class="flex items-center gap-1.5 text-xs text-gray-400 cursor-pointer select-none" title="When on, you can type a custom name right after marking a selection">
      <input
        v-model="pipeline.quickLabel"
        type="checkbox"
        class="accent-blue-500 w-3.5 h-3.5"
      />
      Quick&nbsp;label
    </label>

    <!-- pages -->
    <label class="flex items-center gap-1.5 text-xs text-gray-400">
      Pages
      <input
        :value="pipeline.pages ?? ''"
        type="number"
        min="1"
        placeholder="—"
        class="w-14 bg-gray-800 border border-gray-700 rounded px-2 py-1 text-sm text-gray-200 focus:outline-none focus:ring-1 focus:ring-blue-500"
        @input="(e) => {
          const v = (e.target as HTMLInputElement).value
          pipeline.pages = v ? parseInt(v) : null
        }"
      />
    </label>

    <!-- spacer -->
    <div class="flex-1" />

    <!-- tailor button -->
    <button
      :disabled="!canTailor || pipeline.isTailoring"
      :title="disabledReason || 'Tailor Resume'"
      class="flex items-center gap-2 px-4 py-1.5 rounded-lg font-semibold text-sm transition-colors flex-shrink-0"
      :class="canTailor && !pipeline.isTailoring
        ? 'bg-blue-600 hover:bg-blue-500 text-white cursor-pointer'
        : 'bg-gray-800 text-gray-500 cursor-not-allowed'"
      @click="pipeline.tailor()"
    >
      <svg v-if="pipeline.isTailoring" class="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
      </svg>
      <span>{{ pipeline.isTailoring ? 'Tailoring…' : 'Tailor Resume' }}</span>
    </button>
  </header>
</template>
