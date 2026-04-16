<script setup lang="ts">
import { usePipelineStore } from '../stores/pipeline'

const pipeline = usePipelineStore()

const moddegOptions = [
  { value: 'low', label: 'Low' },
  { value: 'medium-low', label: 'Med-Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'medium-high', label: 'Med-High' },
  { value: 'high', label: 'High' },
]
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
  </header>
</template>
