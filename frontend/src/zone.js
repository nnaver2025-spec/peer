import { ArrowDownRight, ArrowUpRight } from 'lucide-react'

export const THRESHOLD = 1.5
export const TIER_RANK = { strong: 0, moderate: 1, weak: 2, unknown: 3 }

// Z-Score 구간별 강조. 색은 숫자/추이선/바에만 쓰고 컨테이너 배경은 건드리지 않는다.
export function zoneOf(z) {
  if (z >= THRESHOLD) {
    return {
      label: '오버슈팅',
      text: 'text-warn',
      bar: 'bg-warn',
      stroke: '--color-warn',
      Icon: ArrowUpRight,
      note: '국내가 해외보다 과도하게 앞섬',
    }
  }
  if (z <= -THRESHOLD) {
    return {
      label: '언더슈팅',
      text: 'text-accent',
      bar: 'bg-accent',
      stroke: '--color-accent',
      Icon: ArrowDownRight,
      note: '국내 갭 확대, 따라잡기 여지',
    }
  }
  return {
    label: '중립',
    text: 'text-ink',
    bar: 'bg-line-strong',
    stroke: '--color-faint',
    Icon: null,
    note: '통계적 정상 범위',
  }
}

export function isTrusted(group) {
  return TIER_RANK[group.coupling?.tier ?? 'unknown'] <= 1
}

export function signed(value, digits = 2) {
  return `${value > 0 ? '+' : ''}${value.toFixed(digits)}`
}

// RS Rating(국내 유니버스 백분위) 구간. IBD 관행대로 80 이상을 강세로 본다.
export function ratingTone(rating) {
  if (rating >= 80) return 'text-good'
  if (rating >= 50) return 'text-ink'
  return 'text-faint'
}

// 국내 종목은 네이버 금융, 해외는 Yahoo Finance로 연결한다.
export function quoteUrl(ticker) {
  const kr = ticker.match(/^(\d{6})\.(KS|KQ)$/i)
  return kr
    ? `https://finance.naver.com/item/main.naver?code=${kr[1]}`
    : `https://finance.yahoo.com/quote/${encodeURIComponent(ticker)}`
}

// 거래소 접미사별 통화. 접미사가 없으면 미국 상장으로 본다.
const CURRENCY = {
  KS: '₩',
  KQ: '₩',
  T: '¥',
  TW: 'NT$',
  HK: 'HK$',
  SS: '¥',
  SZ: '¥',
  L: '£',
  DE: '€',
  PA: '€',
  AS: '€',
  MI: '€',
  MC: '€',
  HE: '€',
  ST: 'kr',
  OL: 'kr',
  SW: 'CHF',
  TO: 'C$',
  IL: '₪',
}

export function currencyOf(ticker) {
  const suffix = ticker.split('.')[1]
  return (suffix && CURRENCY[suffix.toUpperCase()]) || '$'
}

// 원화처럼 단위가 큰 통화는 소수점을 버린다. 231500.00은 읽기만 어렵다.
export function formatPrice(value, ticker) {
  const symbol = currencyOf(ticker)
  const digits = symbol === '₩' || symbol === '¥' ? 0 : 2
  return `${symbol}${value.toLocaleString('ko-KR', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`
}
