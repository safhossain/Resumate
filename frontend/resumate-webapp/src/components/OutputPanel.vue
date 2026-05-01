<script setup lang="ts">
import { ref } from 'vue'
import { usePipelineStore } from '../stores/pipeline'

const pipeline = usePipelineStore()
const activeTab = ref<'output' | 'changes'>('output')
</script>

<template>
  <div
    v-if="pipeline.latestOutput"
    class="border-t border-gray-800 bg-gray-900/80 max-h-72 overflow-y-auto"
  >
    <!-- sticky header ------------------------------------------------ -->
    <div class="flex items-center justify-between px-5 py-2 border-b border-gray-800 bg-gray-900 sticky top-0 z-10">
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
    <div v-else class="p-5">
      <p
        v-if="pipeline.latestOutput.changes_made"
        class="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap"
      >{{ pipeline.latestOutput.changes_made }}</p>
      <p v-else class="text-sm text-gray-500 italic">No changes summary returned.</p>
    </div>
  </div>
</template>
