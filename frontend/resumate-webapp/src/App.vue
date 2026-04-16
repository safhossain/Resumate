<script setup lang="ts">
import { onMounted } from 'vue'
import TopBar from './components/TopBar.vue'
import SessionPanel from './components/SessionPanel.vue'
import PlaceholderList from './components/PlaceholderList.vue'
import JobPostingPanel from './components/JobPostingPanel.vue'
import DocumentViewer from './components/DocumentViewer.vue'
import OutputPanel from './components/OutputPanel.vue'
import { useSessionStore } from './stores/session'
import { usePipelineStore } from './stores/pipeline'

const session = useSessionStore()
const pipeline = usePipelineStore()

onMounted(() => {
  pipeline.loadModels()
  session.loadSessions()
})
</script>

<template>
  <div class="flex flex-col h-screen bg-gray-950 text-gray-100">    
    <TopBar />
    <!-- main area -->
    <div class="flex flex-1 min-h-0">
      <!-- left sidebar -->
      <aside class="w-96 flex-shrink-0 border-r border-gray-800 flex flex-col overflow-y-auto">
        <SessionPanel />
        <PlaceholderList v-if="session.hasSession" />
        <JobPostingPanel v-if="session.hasSession" />
      </aside>

      <!-- right content -->
      <main class="flex-1 flex flex-col min-w-0">
        <DocumentViewer class="flex-1 min-h-0" />
        <OutputPanel v-if="pipeline.latestOutput" />
      </main>
    </div>
  </div>
</template>
