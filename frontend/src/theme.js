import { useEffect, useState } from 'react'

const STORAGE_KEY = 'peer:theme'
// index.html의 사전 적용 스크립트와 같은 값을 쓴다. 한쪽만 바꾸면 첫 페인트와
// 이후 렌더의 배경색이 어긋난다.
const CANVAS = { dark: '#0e0f11', light: '#ffffff' }

function initialTheme() {
  // index.html이 이미 확정해둔 값을 그대로 받는다. 여기서 다시 읽으면 두 곳의
  // 판단이 갈릴 수 있다.
  const applied = document.documentElement.dataset.theme
  if (applied === 'light' || applied === 'dark') return applied
  // 저장된 선택이 없으면 시스템 설정을 따른다.
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

// 팔레트는 index.css의 :root[data-theme] 토큰이 담당한다. 여기서는 속성만 바꾼다.
export function useTheme() {
  const [theme, setTheme] = useState(initialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute('content', CANVAS[theme])
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      // 저장이 막혀도 이번 세션의 전환은 그대로 동작한다.
    }
  }, [theme])

  const toggle = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))
  return [theme, toggle]
}

// 스킨 비교 실험은 끝났다. 네이티브 톤을 기본으로 확정했으므로 전환 장치는 걷어냈다.
// 실험 중 저장된 선택값이 남아 있으면 지운다. 없는 스킨 속성이 붙은 채로 남으면
// 다음 방문에서 원인을 알 수 없는 차이가 생긴다.
export function clearLegacySkin() {
  try {
    localStorage.removeItem('peer:skin')
  } catch {
    // 저장이 막힌 환경에서는 지울 것도 없다.
  }
  delete document.documentElement.dataset.skin
}
