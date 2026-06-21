<script setup lang="ts">
import { usePipelineStore } from '../stores/pipeline'

const pipeline = usePipelineStore()
</script>

<template>
  <div class="flex flex-col flex-shrink-0 p-4">
    <!-- job posting -->
    <label class="text-xs text-gray-500 mb-1 uppercase tracking-wider">Job Posting</label>
    <textarea
      v-model="pipeline.jobPosting"
      placeholder="Paste job description here…"
      class="min-h-[160px] max-h-[480px] resize-y bg-gray-800/60 border border-gray-700 rounded-lg p-3 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
    />

    <!-- ACC -->
    <label class="text-xs text-gray-500 mt-3 mb-1 uppercase tracking-wider">Additional Context (ACC)</label>
    <textarea
      v-model="pipeline.acc"
      placeholder="Optional extra context for the LLM…"
      class="min-h-[120px] max-h-[400px] resize-y bg-gray-800/60 border border-gray-700 rounded-lg p-3 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:ring-1 focus:ring-blue-500"
    />

    <p v-if="pipeline.error" class="mt-2 text-xs text-red-400">{{ pipeline.error }}</p>
  </div>
</template>
