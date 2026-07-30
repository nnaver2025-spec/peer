import { useEffect, useState } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'
import HotFeed from './HotFeed.jsx'
import MarketMood from './MarketMood.jsx'
import NewsPanel from './NewsPanel.jsx'

// 요약을 고정하지 않고 전체를 한 흐름으로 스크롤한다.
//
// 요약을 상단에 고정했을 때 그것만 508px을 차지해 아래 스크롤 창이 344px로 눌렸다.
// 지수 카드를 펼치거나 뉴스를 보려면 좁은 창 안에서 계속 긁어야 했다. 읽을 내용이
// 늘어난 지금은 한 페이지로 흐르는 편이 낫다.
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
    <main className="flex min-h-0 min-w-0 flex-1 flex-col overflow-y-auto">
      {data.market && (
        <MarketMood
          market={data.market}
          minHits={data.min_sentiment_hits ?? 10}
          indices={data.indices}
          gauge={data.market_gauge}
        />
      )}

      <div className="px-5 py-4">
        {/* 뉴스를 먼저 둔다. 태그율이 41~53%로 커뮤니티(7%)보다 높고 매체가 쓴 글이라
            먼저 읽는 편이 맥락 잡기에 낫다. 커뮤니티 화제글은 그 아래에서 분위기를
            보탠다.

            종목별 점수 표는 여기서 뺐다. 종목 표본은 88.7%가 네이버 한 곳에서 오고
            키워드 3개 차이로 30종목 중 24종목의 구간이 뒤집혔다. 종목 수집은
            시장·섹터 집계 재료로 계속 쓴다. */}
        <NewsPanel news={data.news} />

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
