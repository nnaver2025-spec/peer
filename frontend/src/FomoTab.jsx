import { useEffect, useState } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import HotFeed from './HotFeed.jsx'
import MarketMood from './MarketMood.jsx'

export default function FomoTab() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}fomo_data.json`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then(setData)
      .catch((err) => setError(err.message))
  }, [])

  if (error) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 text-center">
        <div className="max-w-md">
          <AlertTriangle className="mx-auto mb-4 text-warn" aria-hidden="true" />
          <p className="text-ink">fomo_data.json을 불러오지 못했습니다 ({error})</p>
          <p className="mt-3 font-mono text-[13px] text-faint">python fomo_watch.py</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <RefreshCw className="animate-spin text-line-strong" aria-hidden="true" />
      </div>
    )
  }

  // 점검용 부분 수집이 덮이거나 첫 실행이 덜 끝난 상태를 구분해 알린다.
  // 빈 화면만 보여주면 고장인지 데이터가 없는 건지 알 수 없다.
  if (!data.stocks?.length) {
    return (
      <div className="flex flex-1 items-center justify-center px-6 text-center">
        <div className="max-w-md">
          <AlertTriangle className="mx-auto mb-4 text-warn" aria-hidden="true" />
          <p className="text-ink">수집된 종목이 없습니다</p>
          <p className="mt-3 font-mono text-[13px] text-faint">python fomo_watch.py</p>
          <p className="mt-2 text-[12px] text-faint">
            마지막 갱신 {data.generated_at}
          </p>
        </div>
      </div>
    )
  }

  return (
    <main className="flex min-w-0 flex-1 flex-col">
      {data.market && (
        <MarketMood
          market={data.market}
          minHits={data.min_sentiment_hits ?? 10}
          indices={data.indices}
          gauge={data.market_gauge}
        />
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {/* 종목별 점수 표를 여기서 뺐다. 종목 표본은 88.7%가 네이버 한 곳에서 오고
            키워드 3개 차이로 30종목 중 24종목의 구간이 뒤집혔다. 대신 반응이 검증된
            화제글을 둔다. 종목 수집은 시장·섹터 집계 재료로 계속 쓴다. */}
        <HotFeed feed={data.feed ?? []} sources={data.sources} />

        <footer className="tnum mt-8 text-[12px] text-faint">
          generated_at {data.generated_at} · {data.interval_hours}시간 주기 ·{' '}
          {data.sources.length}개 게시판
          {data.lookback_days && ` · 최근 ${data.lookback_days}일`}
          {data.us_index_lookback_days &&
            ` (미국 지수 ${data.us_index_lookback_days}일)`}
          {data.daily_points && ` · 추이 최대 ${data.daily_points}일`}
        </footer>
      </div>
    </main>
  )
}
