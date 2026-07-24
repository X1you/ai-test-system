/**
 * 文件拖拽/选择/校验
 * 扩展名不区分大小写 + 文件大小上限 + MIME 类型校验
 */
import { ref, type Ref } from 'vue'

export interface FileUploadOptions {
  /** 允许的扩展名（不含点，小写），如 ['md', 'txt'] */
  extensions: string[]
  /** 允许的 MIME 类型，如 ['text/plain', 'text/markdown'] */
  mimeTypes?: string[]
  /** 文件大小上限（字节），默认 10MB */
  maxSize?: number
}

export interface FileUploadResult {
  file: File
  error?: string
}

const DEFAULT_MAX_SIZE = 10 * 1024 * 1024 // 10MB

export function useFileUpload(options: FileUploadOptions) {
  const isDragging = ref(false)
  const selectedFile: Ref<File | null> = ref(null)
  const error: Ref<string | null> = ref(null)

  const maxSize = options.maxSize ?? DEFAULT_MAX_SIZE
  const allowedExt = options.extensions.map((e) => e.toLowerCase())
  const allowedMime = options.mimeTypes

  function validateFile(file: File): string | null {
    // 扩展名校验（不区分大小写）
    const ext = file.name.split('.').pop()?.toLowerCase() || ''
    if (!allowedExt.includes(ext)) {
      return `仅支持 .${allowedExt.join(' / .')} 格式的文件`
    }

    // 文件大小校验
    if (file.size > maxSize) {
      const maxMB = (maxSize / 1024 / 1024).toFixed(0)
      return `文件过大（超过 ${maxMB}MB）`
    }

    // MIME 类型校验（如果配置了）
    if (allowedMime && allowedMime.length > 0) {
      // .md 文件浏览器可能给 application/octet-stream，放宽判断
      const isText = file.type === '' ||
        allowedMime.includes(file.type) ||
        file.type.startsWith('text/')
      if (!isText) {
        return `文件类型不正确，仅支持文本文件`
      }
    }

    return null
  }

  function handleFile(file: File): boolean {
    const err = validateFile(file)
    if (err) {
      error.value = err
      selectedFile.value = null
      return false
    }
    error.value = null
    selectedFile.value = file
    return true
  }

  function onDrop(e: DragEvent) {
    isDragging.value = false
    if (e.dataTransfer?.files?.length) {
      return handleFile(e.dataTransfer.files[0])
    }
    return false
  }

  function onDragOver() {
    isDragging.value = true
  }

  function onDragLeave() {
    isDragging.value = false
  }

  function onInputChange(e: Event) {
    const target = e.target as HTMLInputElement
    if (target.files?.length) {
      return handleFile(target.files[0])
    }
    return false
  }

  function reset() {
    selectedFile.value = null
    error.value = null
    isDragging.value = false
  }

  return {
    isDragging,
    selectedFile,
    error,
    validateFile,
    handleFile,
    onDrop,
    onDragOver,
    onDragLeave,
    onInputChange,
    reset,
  }
}
