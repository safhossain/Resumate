import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { TailorResponse, ModelsResponse } from '../api/client'
import {
  tailorResume as apiTailor,
  retryTailor as apiRetry,
  fetchModels as apiFetchModels,
} from '../api/client'
import { useSessionStore } from './session'

export const usePipelineStore = defineStore('pipeline', () => {
  /* ── config ─────────────────────────────────────────────────────── */
  const models = ref<string[]>([])
  const defaultModel = ref<string>('')
  const model = ref<string>('')
  const moddeg = ref<string>('low')
  const faux = ref(false)
  const pages = ref<number | null>(null)
  const jobPosting = ref('')
  const acc = ref('')

  /* ── pipeline state ─────────────────────────────────────────────── */
  const isTailoring = ref(false)
  const isRetrying = ref(false)
  const latestOutput = ref<TailorResponse | null>(null)
  const error = ref<string | null>(null)

  /* ── actions ────────────────────────────────────────────────────── */

  async function loadModels() {
    try {
      const res: ModelsResponse = await apiFetchModels()
      models.value = res.models
      defaultModel.value = res.default_model
      if (!model.value) model.value = res.default_model
    } catch {
      /* backend not reachable yet — leave empty */
    }
  }

  async function tailor() {
    const session = useSessionStore()
    if (!session.sessionId) return
    error.value = null
    isTailoring.value = true
    try {
      latestOutput.value = await apiTailor({
        session_id: session.sessionId,
        job_posting: jobPosting.value,
        acc: acc.value,
        model: model.value || undefined,
        moddeg: moddeg.value,
        faux: faux.value,
        pages: pages.value,
      })
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      isTailoring.value = false
    }
  }

  async function retry() {
    const session = useSessionStore()
    if (!session.sessionId || !latestOutput.value) return
    error.value = null
    isRetrying.value = true
    try {
      latestOutput.value = await apiRetry(
        session.sessionId,
        latestOutput.value.output_id,
      )
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      isRetrying.value = false
    }
  }

  function reset() {
    latestOutput.value = null
    error.value = null
    jobPosting.value = ''
    acc.value = ''
  }

  return {
    models,
    defaultModel,
    model,
    moddeg,
    faux,
    pages,
    jobPosting,
    acc,
    isTailoring,
    isRetrying,
    latestOutput,
    error,
    loadModels,
    tailor,
    retry,
    reset,
  }
})
