import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  DocumentElement,
  PlaceholderResponse,
  SessionSummary,
} from '../api/client'
import {
  uploadFile as apiUpload,
  addPlaceholder as apiAddPh,
  removePlaceholder as apiRemovePh,
  updatePlaceholderType as apiUpdatePhType,
  renamePlaceholder as apiRenamePh,
  reorderPlaceholders as apiReorderPh,
  resizePlaceholder as apiResizePh,
  listSessions as apiListSessions,
  getSession as apiGetSession,
  deleteSession as apiDeleteSession,
  deleteAllSessions as apiDeleteAllSessions,
} from '../api/client'

export function sanitizeKey(raw: string): string {
  let s = raw.toLowerCase().replace(/-/g, '_').replace(/\s+/g, '_')
  s = s.replace(/[^a-z0-9_]/g, '_').replace(/_+/g, '_').replace(/^_+|_+$/g, '')
  return s || 'field'
}

export const useSessionStore = defineStore('session', () => {
  const sessionId = ref<string | null>(null)
  const fileFormat = ref<string>('')
  const originalFilename = ref<string>('')
  const renderedHtml = ref<string>('')
  const rawText = ref<string>('')
  const documentStructure = ref<DocumentElement[]>([])
  const placeholders = ref<Record<string, PlaceholderResponse>>({})
  const texPdfUrl = ref<string | null>(null)
  const isUploading = ref(false)
  const savedSessions = ref<SessionSummary[]>([])

  /**
   * Cross-component signal: ask the placeholder list to scroll a given
   * placeholder into view (top-aligned when possible). A fresh object is
   * emitted each time so repeat clicks of the same key still trigger.
   */
  const scrollRequest = ref<{ key: string; nonce: number } | null>(null)
  let _scrollNonce = 0
  function requestScrollToPlaceholder(key: string) {
    _scrollNonce += 1
    scrollRequest.value = { key, nonce: _scrollNonce }
  }

  /**
   * Reciprocal of `scrollRequest`: ask the document viewer to scroll a given
   * placeholder's highlight into view (clicked from the placeholder list).
   */
  const scrollToHighlight = ref<{ key: string; nonce: number } | null>(null)
  let _highlightNonce = 0
  function requestScrollToHighlight(key: string) {
    _highlightNonce += 1
    scrollToHighlight.value = { key, nonce: _highlightNonce }
  }

  const hasSession = computed(() => sessionId.value !== null)
  const placeholderList = computed(() => Object.values(placeholders.value))
  const tailorPlaceholders = computed(() =>
    placeholderList.value.filter((p) => p.type === 'tailor'),
  )
  const sensitivePlaceholders = computed(() =>
    placeholderList.value.filter((p) => p.type === 'sensitive'),
  )

  function reset() {
    sessionId.value = null
    fileFormat.value = ''
    originalFilename.value = ''
    renderedHtml.value = ''
    rawText.value = ''
    documentStructure.value = []
    placeholders.value = {}
    texPdfUrl.value = null
  }

  async function upload(file: File) {
    isUploading.value = true
    try {
      const res = await apiUpload(file)
      sessionId.value = res.session_id
      fileFormat.value = res.file_format
      originalFilename.value = file.name
      renderedHtml.value = res.rendered_html
      rawText.value = res.raw_text
      documentStructure.value = res.document_structure
      texPdfUrl.value = res.tex_pdf_url
      placeholders.value = {}
    } finally {
      isUploading.value = false
    }
  }

  async function addPlaceholder(
    selectedText: string,
    startOffset: number,
    endOffset: number,
    type: 'tailor' | 'sensitive',
    key?: string,
    value?: string,
  ) {
    if (!sessionId.value) return
    const ph = await apiAddPh({
      session_id: sessionId.value,
      selected_text: selectedText,
      start_offset: startOffset,
      end_offset: endOffset,
      type,
      key,
      value,
    })
    placeholders.value = { ...placeholders.value, [ph.key]: ph }
    return ph
  }

  async function removePlaceholder(key: string) {
    if (!sessionId.value) return
    await apiRemovePh(sessionId.value, key)
    const copy = { ...placeholders.value }
    delete copy[key]
    placeholders.value = copy
  }

  async function renamePlaceholder(oldKey: string, newKey: string) {
    if (!sessionId.value || !placeholders.value[oldKey]) return
    const updated = await apiRenamePh(sessionId.value, oldKey, newKey)
    // Rebuild preserving order so the renamed row keeps its position
    // instead of jumping to the bottom.
    const rebuilt: Record<string, PlaceholderResponse> = {}
    for (const [k, v] of Object.entries(placeholders.value)) {
      if (k === oldKey) rebuilt[updated.key] = updated
      else rebuilt[k] = v
    }
    placeholders.value = rebuilt
  }

  async function togglePlaceholderType(key: string) {
    if (!sessionId.value || !placeholders.value[key]) return
    const current = placeholders.value[key].type
    const newType = current === 'tailor' ? 'sensitive' : 'tailor'
    const updated = await apiUpdatePhType(sessionId.value, key, newType as 'tailor' | 'sensitive')
    placeholders.value = { ...placeholders.value, [key]: updated }
  }

  function updatePlaceholderValue(key: string, value: string) {
    if (!placeholders.value[key]) return
    placeholders.value = {
      ...placeholders.value,
      [key]: { ...placeholders.value[key], value },
    }
  }

  /**
   * Move an existing placeholder's start/end boundary. Throws on 409 (overlap)
   * so the caller can revert + flash; on success the map is updated in place.
   */
  async function resizePlaceholder(key: string, start: number, end: number) {
    if (!sessionId.value || !placeholders.value[key]) return
    const updated = await apiResizePh(sessionId.value, key, start, end)
    placeholders.value = { ...placeholders.value, [key]: updated }
    return updated
  }

  async function reorderPlaceholders(orderedKeys: string[]) {
    if (!sessionId.value) return
    const current = placeholders.value
    const rebuilt: Record<string, PlaceholderResponse> = {}
    for (const k of orderedKeys) {
      if (current[k]) rebuilt[k] = current[k]
    }
    // Safety: keep any key not present in the supplied order.
    for (const k of Object.keys(current)) {
      if (!(k in rebuilt)) rebuilt[k] = current[k]
    }
    placeholders.value = rebuilt // optimistic — list reflects new order immediately
    try {
      await apiReorderPh(sessionId.value, Object.keys(rebuilt))
    } catch {
      /* keep optimistic order; backend resyncs on next session load */
    }
  }

  async function loadSessions() {
    savedSessions.value = await apiListSessions()
  }

  async function loadSession(id: string) {
    const data = await apiGetSession(id)
    sessionId.value = data.session_id
    fileFormat.value = data.file_format
    originalFilename.value = data.original_filename
    renderedHtml.value = data.rendered_html
    rawText.value = data.raw_text
    documentStructure.value = data.document_structure
    placeholders.value = data.placeholders as Record<string, PlaceholderResponse>
    texPdfUrl.value = data.tex_pdf_url

    // Restore persisted ACC into the pipeline store (lazy import avoids circular dep)
    const { usePipelineStore } = await import('./pipeline')
    usePipelineStore().acc = data.acc ?? ''
  }

  async function removeSession(id: string) {
    await apiDeleteSession(id)
    savedSessions.value = savedSessions.value.filter((s) => s.session_id !== id)
    if (sessionId.value === id) reset()
  }

  async function removeAllSessions() {
    await apiDeleteAllSessions()
    savedSessions.value = []
    reset()
  }

  return {
    sessionId,
    fileFormat,
    originalFilename,
    renderedHtml,
    rawText,
    documentStructure,
    placeholders,
    texPdfUrl,
    isUploading,
    savedSessions,
    hasSession,
    placeholderList,
    tailorPlaceholders,
    sensitivePlaceholders,
    reset,
    upload,
    addPlaceholder,
    removePlaceholder,
    renamePlaceholder,
    togglePlaceholderType,
    updatePlaceholderValue,
    reorderPlaceholders,
    resizePlaceholder,
    scrollRequest,
    requestScrollToPlaceholder,
    scrollToHighlight,
    requestScrollToHighlight,
    loadSessions,
    loadSession,
    removeSession,
    removeAllSessions,
  }
})
