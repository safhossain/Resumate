<script setup lang="ts">
import { useSessionStore } from '../stores/session'

const session = useSessionStore()
</script>

<template>
  <div class="p-4 border-b border-gray-800" v-if="session.placeholderList.length">
    <p class="text-xs text-gray-500 mb-2 uppercase tracking-wider">Placeholders</p>

    <ul class="space-y-1.5 max-h-56 overflow-y-auto">
      <li
        v-for="ph in session.placeholderList"
        :key="ph.key"
        class="flex items-start gap-2 text-sm px-2 py-1.5 rounded bg-gray-800/40"
      >
        <!-- type toggle -->
        <button
          class="mt-0.5 w-4 h-4 rounded-full flex-shrink-0 flex items-center justify-center transition-colors"
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
          <!-- key -->
          <span
            class="font-mono text-xs"
            :class="ph.type === 'tailor' ? 'text-blue-400' : 'text-amber-400'"
          >
            {{ ph.key }}
          </span>

          <!-- selected text preview -->
          <p class="text-[11px] text-gray-500 truncate mt-0.5">{{ ph.selected_text }}</p>

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
