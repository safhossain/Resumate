<script setup lang="ts">
import { ref } from 'vue'
import { useSessionStore } from '../stores/session'
import { usePipelineStore } from '../stores/pipeline'

const session = useSessionStore()
const pipeline = usePipelineStore()
const dragOver = ref(false)

function onDrop(e: DragEvent) {
  dragOver.value = false
  const file = e.dataTransfer?.files[0]
  if (file) handleFile(file)
}

function onFileInput(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (file) handleFile(file)
  input.value = ''
}

async function handleFile(file: File) {
  pipeline.reset()
  await session.upload(file)
}

async function openSession(id: string) {
  pipeline.reset()
  await session.loadSession(id)
}
</script>

<template>
  <div class="p-4 border-b border-gray-800">
    <!-- upload dropzone -->
    <div
      class="border-2 border-dashed rounded-lg p-6 text-center transition-colors"
      :class="dragOver
        ? 'border-blue-400 bg-blue-500/10'
        : 'border-gray-700 hover:border-gray-500'"
      @dragover.prevent="dragOver = true"
      @dragleave="dragOver = false"
      @drop.prevent="onDrop"
    >
      <div v-if="session.isUploading" class="text-gray-400 text-sm animate-pulse">
        Processing…
      </div>
      <div v-else>
        <p class="text-sm text-gray-400 mb-2">
          Drop a <span class="text-gray-200 font-medium">.docx</span>,
          <span class="text-gray-200 font-medium">.txt</span>, or
          <span class="text-gray-200 font-medium">.tex</span> file
        </p>
        <label class="inline-block px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-sm rounded cursor-pointer transition-colors">
          Browse
          <input type="file" accept=".docx,.txt,.tex" class="hidden" @change="onFileInput" />
        </label>
      </div>
    </div>

    <!-- current session -->
    <div v-if="session.hasSession" class="mt-3 text-xs text-gray-500">
      <span class="text-gray-300">{{ session.originalFilename }}</span>
      <span class="ml-1.5 px-1.5 py-0.5 bg-gray-800 rounded text-gray-400 uppercase text-[10px]">
        {{ session.fileFormat }}
      </span>
    </div>

    <!-- saved sessions -->
    <div v-if="session.savedSessions.length" class="mt-4">
      <div class="flex items-center justify-between mb-1.5">
        <p class="text-xs text-gray-500 uppercase tracking-wider">Saved sessions</p>
        <button
          class="text-[10px] text-red-500/70 hover:text-red-400 transition-colors"
          @click="session.removeAllSessions()"
        >
          Delete all
        </button>
      </div>
      <ul class="space-y-1 max-h-32 overflow-y-auto">
        <li
          v-for="s in session.savedSessions"
          :key="s.session_id"
          class="group flex items-center justify-between text-sm px-2 py-1 rounded hover:bg-gray-800/60 cursor-pointer transition-colors"
          :class="{ 'bg-gray-800': s.session_id === session.sessionId }"
          @click="openSession(s.session_id)"
        >
          <span class="truncate">{{ s.name || s.original_filename }}</span>
          <div class="flex items-center gap-1.5 flex-shrink-0 ml-2">
            <span class="text-[10px] text-gray-600">
              {{ s.placeholder_count }} ph
            </span>
            <button
              class="text-gray-700 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all text-xs"
              title="Delete session"
              @click.stop="session.removeSession(s.session_id)"
            >
              ✕
            </button>
          </div>
        </li>
      </ul>
    </div>
  </div>
</template>
