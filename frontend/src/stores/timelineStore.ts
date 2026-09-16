// stores/timelineStore.ts — Controlo temporal da linha cronológica
import { defineStore } from 'pinia'
import { ref, computed, readonly } from 'vue'

const AVAILABLE_YEARS = [
  1985, 1990, 1995, 2000, 2005, 2010, 2015, 2018, 2020, 2022, 2023, 2024,
]

export const useTimelineStore = defineStore('timeline', () => {
  const selectedYear = ref<number>(2024)
  const availableYears = ref<number[]>(AVAILABLE_YEARS)
  const isAnimating = ref(false)
  const animationSpeed = ref<'slow' | 'normal' | 'fast'>('normal')

  let animationTimer: ReturnType<typeof setInterval> | null = null

  const selectedYearIndex = computed(() =>
    availableYears.value.indexOf(selectedYear.value)
  )

  const canGoBack = computed(() => selectedYearIndex.value > 0)
  const canGoForward = computed(
    () => selectedYearIndex.value < availableYears.value.length - 1
  )

  function setYear(year: number) {
    if (availableYears.value.includes(year)) {
      selectedYear.value = year
    }
  }

  function stepBack() {
    if (canGoBack.value) {
      selectedYear.value = availableYears.value[selectedYearIndex.value - 1]
    }
  }

  function stepForward() {
    if (canGoForward.value) {
      selectedYear.value = availableYears.value[selectedYearIndex.value + 1]
    }
  }

  function startAnimation() {
    if (isAnimating.value) return
    isAnimating.value = true

    const delay = { slow: 1500, normal: 800, fast: 400 }[animationSpeed.value]
    animationTimer = setInterval(() => {
      if (canGoForward.value) {
        stepForward()
      } else {
        stopAnimation()
        selectedYear.value = availableYears.value[0] // Reinicia
      }
    }, delay)
  }

  function stopAnimation() {
    isAnimating.value = false
    if (animationTimer) {
      clearInterval(animationTimer)
      animationTimer = null
    }
  }

  return {
    selectedYear: readonly(selectedYear),
    availableYears: readonly(availableYears),
    isAnimating: readonly(isAnimating),
    animationSpeed,
    canGoBack,
    canGoForward,
    setYear,
    stepBack,
    stepForward,
    startAnimation,
    stopAnimation,
  }
})
