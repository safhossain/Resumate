<script setup lang="ts">
import { computed } from 'vue'
import { usePipelineStore } from '../stores/pipeline'
import { useSessionStore } from '../stores/session'

const pipeline = usePipelineStore()
const session = useSessionStore()

const canTailor = computed(
  () => session.hasSession && session.placeholderList.length > 0 && pipeline.jobPosting.trim().length > 0,
)
</script>

<template>
  <div class="flex flex-col flex-1 min-h-0 p-4">
    <!-- job posting -->
    <label class="text-xs text-gray-500 mb-1 uppercase tracking-wider">Job Posting</label>
    <textarea
      v-model="pipeline.jobPosting"
      placeholder="Paste job description here…"
      class="flex-1 min-h-[120px] resize-none bg-gray-800/60 border border-gray-700 rounded-lg p-3 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
    />

    <!-- ACC -->
    <label class="text-xs text-gray-500 mt-3 mb-1 uppercase tracking-wider">Additional Context (ACC)</label>
    <textarea
      v-model="pipeline.acc"
      placeholder="Optional extra context for the LLM…"
      rows="3"
      class="resize-none bg-gray-800/60 border border-gray-700 rounded-lg p-3 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
    />

    <!-- tailor button -->
    <button
      :disabled="!canTailor || pipeline.isTailoring"
      class="mt-4 w-full py-2.5 rounded-lg font-semibold text-sm transition-colors"
      :class="canTailor && !pipeline.isTailoring
        ? 'bg-blue-600 hover:bg-blue-500 text-white cursor-pointer'
        : 'bg-gray-800 text-gray-500 cursor-not-allowed'"
      @click="pipeline.tailor()"
    >
      <span v-if="pipeline.isTailoring" class="inline-flex items-center gap-2">
        <svg class="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        Tailoring…
      </span>
      <span v-else>Tailor Resume</span>
    </button>

    <p v-if="pipeline.error" class="mt-2 text-xs text-red-400">{{ pipeline.error }}</p>
  </div>
</template>
