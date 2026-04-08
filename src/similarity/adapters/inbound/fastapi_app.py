"""
유사 종목 탐색 + 백테스트 FastAPI 인바운드 어댑터.

WHY: 헥사고날 아키텍처에서 HTTP 관심사(라우팅·직렬화·에러 변환)와
     도메인 로직을 분리한다. 이 파일은 포트에만 의존하므로
     인프라 교체(Flask, gRPC 등) 시 도메인 코드를 건드리지 않아도 된다.
     strategy_factory 를 주입받아 요청마다 가중치 기반 전략을 동적으로 생성한다.
     /backtest/pair 엔드포인트는 조립 루트로서 trading_signal 과 backtest
     두 L3 모듈을 결합한다 — 어댑터 레이어이므로 허용된다.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Callable, Literal, Mapping

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from backtest.adapters.outbound.in_memory_backtest_engine import InMemoryBacktestEngine
from backtest.application.ports.position_sizer import PositionSizer
from backtest.domain.backtest_config import BacktestConfig
from backtest.domain.price_bar import PriceBar
from market_data.application.ports import PriceRepository
from market_data.domain.adjusted_price import AdjustedPrice
from market_data.domain.market import Market
from market_data.domain.ticker import Ticker
from similarity.adapters.inbound._signal_conversion import trading_signal_to_backtest_signal
from similarity.application.find_similar_tickers import FindSimilarQuery, FindSimilarTickers
from similarity.application.ports import SimilarityStrategy
from similarity.domain.pearson import pearson_correlation
from similarity.domain.weighted_sum_strategy import SimilarityWeights
from trading_signal.adapters.outbound.pair_trading_signal_source import PairTradingSignalSource
from trading_signal.application.use_cases.generate_pair_signals import PairSignalConfig
from trading_signal.domain.pair import Pair
from universe.application.ports import UniverseSource

# /portfolio/compute 전략 이름 상수
_STRATEGY_EQUAL_WEIGHT = "equal_weight"
_STRATEGY_SCORE_WEIGHTED = "score_weighted"

# /similar 유사도 전략 이름 상수
_SIM_STRATEGY_WEIGHTED_SUM = "weighted_sum"
_SIM_STRATEGY_SPEARMAN = "spearman"
_SIM_STRATEGY_COINTEGRATION = "cointegration"

# 에러 메시지 식별자 — 매직 문자열 금지
_ERR_NOT_IN_UNIVERSE = "유니버스에 없습니다"
# WHY: 시계열 부재는 아직 데이터가 없는 상태이므로 빈 results 로 처리해
#      클라이언트가 404/400 없이 빈 목록을 수신할 수 있도록 한다.
_ERR_SERIES_MISSING = "시계열 없음"
_ERR_SERIES_NOT_FOUND_A = "a 시계열 없음"
_ERR_SERIES_NOT_FOUND_B = "b 시계열 없음"
_ERR_INSUFFICIENT_INTERSECTION = "교집합이 부족"

# 쿼리 파라미터 기본값 상수
_DEFAULT_TOP_K = 10
_DEFAULT_MIN_ABS_SCORE = 0.0
_DEFAULT_W1 = 0.5
_DEFAULT_W2 = 0.3
_DEFAULT_W3 = 0.2

# pair 엔드포인트 롤링 윈도우 크기
_PAIR_ROLLING_WINDOW = 20

# 교집합 계산에 필요한 최소 날짜 수 (log_returns 가 1개 이상이려면 최소 2개 필요)
_MIN_INTERSECTION_SIZE = 2

# PositionSizer 선택 리터럴 타입 — 확장 시 여기에 추가
_SIZER_STRENGTH = "strength"
_SIZER_EQUAL_WEIGHT = "equal_weight"
_SIZER_SCORE_WEIGHTED = "score_weighted"

# 리밸런싱 엔드포인트 기본값 상수
_MIN_TRADE_WEIGHT_DEFAULT = 0.01

# 백테스트 엔드포인트 기본값 상수
_BACKTEST_DEFAULT_LOOKBACK = 20
_BACKTEST_DEFAULT_ENTRY = 1.5
_BACKTEST_DEFAULT_EXIT = 0.5
# WHY: KRW 기준 개인 계좌 스케일(1천만원). 한국 주식 주당가가 수만~수십만원이라
#      기존 10_000(USD 가정)로는 1주도 체결되지 않아 백테스트가 사실상 무의미했다.
_BACKTEST_DEFAULT_INITIAL = 10_000_000.0
_BACKTEST_DEFAULT_FEE = 0.001
_BACKTEST_DEFAULT_SLIPPAGE = 5.0
# 무위험 수익률 기본값 — 연환산 비율 (0 = 무위험 수익 없음)
_BACKTEST_DEFAULT_RFR = 0.0
# 포트폴리오 제약 기본값 — equal_weight 사이저 선택 시에만 의미 있음
_BACKTEST_DEFAULT_MAX_POSITION_WEIGHT = 1.0
_BACKTEST_DEFAULT_CASH_BUFFER = 0.0


# ── 리밸런싱 요청/응답 DTO ─────────────────────────────────────────────────

class PositionInput(BaseModel):
    """현재 보유 포지션 입력 DTO."""

    symbol: str
    quantity: float
    market_value: float


class TargetInput(BaseModel):
    """목표 비중 입력 DTO."""

    symbol: str
    weight: float


class RebalanceRequest(BaseModel):
    """POST /portfolio/rebalance 요청 바디."""

    current_positions: list[PositionInput]
    target_weights: list[TargetInput]
    total_equity: float
    min_trade_weight: float = _MIN_TRADE_WEIGHT_DEFAULT
    # WHY: 선택적 제약 검증. None 이면 기존 동작 유지, 주입 시 위반하면 400 반환.
    max_position_weight: float | None = None
    cash_buffer: float | None = None


class OrderIntentResponse(BaseModel):
    """단일 주문 의도 응답 DTO."""

    symbol: str
    delta_weight: float
    side: Literal["BUY", "SELL"]


class RebalanceResponse(BaseModel):
    """POST /portfolio/rebalance 응답 바디."""

    intents: list[OrderIntentResponse]


# ── 목표 비중 계산 요청/응답 DTO ──────────────────────────────────────────────

class SignalInputDto(BaseModel):
    """단일 시그널 입력 DTO."""

    symbol: str
    score: float  # >= 0


class ComputeWeightsRequest(BaseModel):
    """POST /portfolio/compute 요청 바디."""

    signals: list[SignalInputDto]
    strategy: Literal["equal_weight", "score_weighted"] = "equal_weight"
    max_position_weight: float = 1.0  # (0, 1]
    cash_buffer: float = 0.0  # [0, 1)


class TargetWeightResponse(BaseModel):
    """단일 목표 비중 응답 DTO."""

    symbol: str
    weight: float


class PairRef(BaseModel):
    """배치 백테스트의 단일 페어 식별자."""

    a: str
    b: str


class BatchBacktestRequest(BaseModel):
    """POST /backtest/batch 요청 바디."""

    pairs: list[PairRef]
    lookback: int = _BACKTEST_DEFAULT_LOOKBACK
    entry: float = _BACKTEST_DEFAULT_ENTRY
    exit: float = _BACKTEST_DEFAULT_EXIT
    initial: float = _BACKTEST_DEFAULT_INITIAL
    fee: float = _BACKTEST_DEFAULT_FEE
    slippage: float = _BACKTEST_DEFAULT_SLIPPAGE
    rfr: float = _BACKTEST_DEFAULT_RFR
    sizer: Literal["strength", "equal_weight", "score_weighted"] = "strength"
    max_position_weight: float = _BACKTEST_DEFAULT_MAX_POSITION_WEIGHT
    cash_buffer: float = _BACKTEST_DEFAULT_CASH_BUFFER


class ComputeWeightsResponse(BaseModel):
    """POST /portfolio/compute 응답 바디."""

    weights: list[TargetWeightResponse]


def create_app(
    repository: PriceRepository,
    universe_source: UniverseSource,
    strategy_factory: Callable[[SimilarityWeights], SimilarityStrategy],
    strategy_registry: Mapping[str, SimilarityStrategy] | None = None,
) -> FastAPI:
    """FastAPI 앱 인스턴스를 생성하고 라우트를 등록한다.

    WHY: 앱 팩토리 패턴으로 의존성을 클로저에 캡처해
         테스트마다 독립적인 Fake 인스턴스를 주입할 수 있도록 한다.
         strategy_factory 는 요청별로 가중치를 받아 전략을 동적으로 생성한다.

    Args:
        repository: 가격 시계열 저장소 포트
        universe_source: 유니버스 스냅샷 조회 포트
        strategy_factory: SimilarityWeights 를 받아 SimilarityStrategy 를 반환하는 팩토리
    """
    # WHY: strategy_registry 가 None 이면 빈 dict 로 정규화해 조회 분기를 단순화한다.
    _registry: Mapping[str, SimilarityStrategy] = strategy_registry or {}

    app = FastAPI()

    @app.get("/health")
    def health() -> dict:
        """로드밸런서 헬스 프로브용 엔드포인트."""
        return {"status": "ok"}

    @app.get("/meta/universe")
    def universe_meta_endpoint(
        name: str = Query("M1_PLACEHOLDER"),
        as_of: date | None = Query(None),
    ) -> dict:
        """UI 드롭다운용 유니버스 스냅샷 — 시장별 종목 목록.

        WHY: 프런트가 하드코딩 없이 실제 DB 의 시드 유니버스를 드롭다운/체크박스
             소스로 쓰게 한다. 시장별로 그룹핑해 UI 가 시장 필터를 즉시 구성할 수 있다.
             KRX 종목 코드→이름 매핑은 프런트가 추가 API 없이 보조 맵으로 처리한다.
        """
        snapshot = universe_source.fetch(name, as_of or date.today())
        groups: dict[str, list[dict]] = {}
        for ticker in snapshot.tickers:
            groups.setdefault(ticker.market.value, []).append(
                {"symbol": ticker.symbol, "market": ticker.market.value}
            )
        return {
            "name": snapshot.name,
            "as_of": snapshot.as_of.isoformat(),
            "total": len(snapshot.tickers),
            "markets": sorted(groups.keys()),
            "by_market": groups,
        }

    @app.get("/meta/backtest-params")
    def backtest_params_meta_endpoint() -> dict:
        """백테스트 변수 메타정보 — UI 인라인 설명/기본값/단위 제공.

        WHY: 프런트에 하드코딩된 설명을 단일 진실원(API)에서 내려받으면
             쿼리/파라미터 설명이 서버 코드와 자동 동기화된다. UI 는 이 스키마를
             읽어 라벨·툴팁·기본값·단위를 렌더링한다.
        """
        return {
            "params": [
                {
                    "key": "lookback",
                    "label": "Z-score 롤링 윈도우",
                    "description": "스프레드의 평균·표준편차를 계산하는 거래일 수. 값이 클수록 평균회귀가 느려집니다.",
                    "type": "int",
                    "unit": "거래일",
                    "default": _BACKTEST_DEFAULT_LOOKBACK,
                    "min": 5,
                    "max": 120,
                },
                {
                    "key": "entry",
                    "label": "진입 Z-score 임계값",
                    "description": "|z| 가 이 값을 넘으면 페어 진입 신호가 발생합니다. 클수록 진입이 보수적입니다.",
                    "type": "float",
                    "unit": "σ",
                    "default": _BACKTEST_DEFAULT_ENTRY,
                },
                {
                    "key": "exit",
                    "label": "청산 Z-score 임계값",
                    "description": "|z| 가 이 값 이하로 수렴하면 포지션을 청산합니다.",
                    "type": "float",
                    "unit": "σ",
                    "default": _BACKTEST_DEFAULT_EXIT,
                },
                {
                    "key": "initial",
                    "label": "초기 자본",
                    "description": "백테스트 시작 시 투입하는 현금. KRW 기준 개인 계좌 스케일이 기본값입니다.",
                    "type": "float",
                    "unit": "KRW",
                    "default": _BACKTEST_DEFAULT_INITIAL,
                },
                {
                    "key": "fee",
                    "label": "거래 수수료율",
                    "description": "체결 금액 대비 수수료 비율(양방향 개별 적용).",
                    "type": "float",
                    "unit": "비율(0.001 = 0.1%)",
                    "default": _BACKTEST_DEFAULT_FEE,
                },
                {
                    "key": "slippage",
                    "label": "슬리피지",
                    "description": "체결가 왜곡 추정치(basis point). 클수록 비용 가정이 보수적입니다.",
                    "type": "float",
                    "unit": "bps",
                    "default": _BACKTEST_DEFAULT_SLIPPAGE,
                },
                {
                    "key": "rfr",
                    "label": "무위험 수익률",
                    "description": "Sharpe/Sortino 분모에 차감되는 연환산 무위험 수익률.",
                    "type": "float",
                    "unit": "연이율(0.03 = 3%)",
                    "default": _BACKTEST_DEFAULT_RFR,
                },
                {
                    "key": "sizer",
                    "label": "포지션 사이저",
                    "description": "자본 배분 방식. strength=신호 강도 비례, equal_weight=동일 가중, score_weighted=스코어 가중.",
                    "type": "enum",
                    "options": ["strength", "equal_weight", "score_weighted"],
                    "default": "strength",
                },
                {
                    "key": "max_position_weight",
                    "label": "단일 종목 최대 비중",
                    "description": "포트폴리오 내 단일 종목의 자본 비중 상한(equal/score_weighted 에만 적용).",
                    "type": "float",
                    "unit": "비율(0~1)",
                    "default": _BACKTEST_DEFAULT_MAX_POSITION_WEIGHT,
                },
                {
                    "key": "cash_buffer",
                    "label": "현금 버퍼",
                    "description": "총자본 중 투자에 사용하지 않고 유보할 현금 비율.",
                    "type": "float",
                    "unit": "비율(0~1)",
                    "default": _BACKTEST_DEFAULT_CASH_BUFFER,
                },
                {
                    "key": "risk_position_limit",
                    "label": "리스크: 포지션 한도",
                    "description": "단일 종목 노출 한도. 초과 진입 후보를 차단합니다(선택).",
                    "type": "float",
                    "unit": "비율(0~1)",
                    "default": None,
                },
                {
                    "key": "risk_max_drawdown",
                    "label": "리스크: 최대 드로다운",
                    "description": "세션 peak 대비 누적 하락이 한도를 넘으면 신규 진입을 차단합니다(선택).",
                    "type": "float",
                    "unit": "비율(0~1)",
                    "default": None,
                },
                {
                    "key": "risk_daily_loss",
                    "label": "리스크: 일일 손실 한도",
                    "description": "당일 시작 대비 손실이 한도를 넘으면 신규 진입을 차단합니다(선택).",
                    "type": "float",
                    "unit": "비율(0~1)",
                    "default": None,
                },
                {
                    "key": "risk_stop_loss",
                    "label": "리스크: 손절률",
                    "description": "개별 포지션 손실률이 한도를 넘으면 즉시 강제 청산합니다(선택).",
                    "type": "float",
                    "unit": "비율(0~1)",
                    "default": None,
                },
            ]
        }

    @app.get("/similar/{symbol}")
    def find_similar_endpoint(
        symbol: str,
        market: str = Query(...),
        universe: str = Query(...),
        as_of: date = Query(...),
        top_k: int = Query(_DEFAULT_TOP_K),
        min_abs_score: float = Query(_DEFAULT_MIN_ABS_SCORE),
        w1: float = Query(_DEFAULT_W1),
        w2: float = Query(_DEFAULT_W2),
        w3: float = Query(_DEFAULT_W3),
        strategy_name: Literal[
            "weighted_sum", "spearman", "cointegration"
        ] = Query(_SIM_STRATEGY_WEIGHTED_SUM, alias="strategy"),
    ) -> dict:
        """유사 종목 목록을 반환한다.

        WHY: strategy 쿼리 파라미터로 런타임에 유사도 공식을 교체할 수 있다.
             weighted_sum 은 w1/w2/w3 가중치를 사용하고, spearman/cointegration
             은 registry 에서 사전 구축된 인스턴스를 조회한다.
        """
        try:
            weights = SimilarityWeights(w1, w2, w3)
            if strategy_name == _SIM_STRATEGY_WEIGHTED_SUM:
                strategy = strategy_factory(weights)
            else:
                if strategy_name not in _registry:
                    raise HTTPException(
                        status_code=400,
                        detail=f"strategy '{strategy_name}' 가 등록되지 않았습니다",
                    )
                strategy = _registry[strategy_name]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        find_similar = FindSimilarTickers(
            repository=repository,
            universe_source=universe_source,
            strategy=strategy,
        )
        target = Ticker(market=Market(market.upper()), symbol=symbol)
        query = FindSimilarQuery(
            target=target,
            universe_name=universe,
            as_of=as_of,
            top_k=top_k,
            min_abs_score=min_abs_score,
        )
        return _execute_query(find_similar, query, target, weights, repository)

    @app.get("/pair/{symbol_a}/{symbol_b}")
    def pair_endpoint(
        symbol_a: str,
        symbol_b: str,
        market_a: str = Query(...),
        market_b: str = Query(...),
        as_of: date = Query(...),
    ) -> dict:
        """두 종목의 log_returns 와 rolling Pearson 상관계수를 반환한다.

        WHY: 시각화 플레이그라운드에서 두 종목의 가격 동조화 수준을 직관적으로
             확인하기 위해 교집합 날짜 기준 log_returns 와 rolling correlation 을 제공한다.
             교집합을 사용하는 이유: 두 시계열의 날짜가 다를 수 있으므로
             공통 날짜에서만 수익률을 동기화해야 일대일 비교가 가능하다.
        """
        ticker_a = Ticker(Market(market_a.upper()), symbol_a)
        ticker_b = Ticker(Market(market_b.upper()), symbol_b)

        series_a = repository.load(ticker_a)
        if series_a is None:
            raise HTTPException(status_code=404, detail=f"{ticker_a}: {_ERR_SERIES_NOT_FOUND_A}")

        series_b = repository.load(ticker_b)
        if series_b is None:
            raise HTTPException(status_code=404, detail=f"{ticker_b}: {_ERR_SERIES_NOT_FOUND_B}")

        common_dates, prices_a, prices_b = _intersect_series(series_a, series_b)

        if len(common_dates) < _MIN_INTERSECTION_SIZE:
            raise HTTPException(status_code=400, detail=_ERR_INSUFFICIENT_INTERSECTION)

        returns_a = _to_log_returns(prices_a)
        returns_b = _to_log_returns(prices_b)
        return_dates = common_dates[1:]

        rolling_values = _compute_rolling_corr(returns_a, returns_b, _PAIR_ROLLING_WINDOW)

        return {
            "a": str(ticker_a),
            "b": str(ticker_b),
            "dates": [d.isoformat() for d in return_dates],
            "log_returns_a": returns_a,
            "log_returns_b": returns_b,
            "rolling_corr": {"window": _PAIR_ROLLING_WINDOW, "values": rolling_values},
        }

    @app.get("/backtest/pair/{a}/{b}")
    def backtest_pair_endpoint(
        a: str,
        b: str,
        lookback: int = Query(_BACKTEST_DEFAULT_LOOKBACK),
        entry: float = Query(_BACKTEST_DEFAULT_ENTRY),
        exit_: float = Query(_BACKTEST_DEFAULT_EXIT, alias="exit"),
        initial: float = Query(_BACKTEST_DEFAULT_INITIAL),
        fee: float = Query(_BACKTEST_DEFAULT_FEE),
        slippage: float = Query(_BACKTEST_DEFAULT_SLIPPAGE),
        rfr: float = Query(_BACKTEST_DEFAULT_RFR, ge=0.0, le=1.0, description="연환산 무위험 수익률"),
        sizer: Literal["strength", "equal_weight", "score_weighted"] = Query(
            _SIZER_STRENGTH,
            description="포지션 사이징 방식 (strength: 신호 강도 비례, equal_weight: 균등 비중, score_weighted: 스코어 가중)",
        ),
        max_position_weight: float = Query(
            _BACKTEST_DEFAULT_MAX_POSITION_WEIGHT,
            gt=0.0,
            le=1.0,
            description="최대 포지션 비중 (0~1). equal_weight 사이저 선택 시에만 적용.",
        ),
        cash_buffer: float = Query(
            _BACKTEST_DEFAULT_CASH_BUFFER,
            ge=0.0,
            lt=1.0,
            description="현금 버퍼 비율 (0~1). equal_weight 사이저 선택 시에만 적용.",
        ),
        risk_position_limit: float | None = Query(
            None, gt=0.0, le=1.0,
            description="리스크 가드: 단일 심볼 최대 비중. 미지정 시 비활성.",
        ),
        risk_max_drawdown: float | None = Query(
            None, gt=0.0, le=1.0,
            description="리스크 가드: 누적 DD 한도. 초과 시 신규 진입 차단.",
        ),
        risk_daily_loss: float | None = Query(
            None, gt=0.0, le=1.0,
            description="리스크 가드: 당일 손실 한도.",
        ),
        risk_stop_loss: float | None = Query(
            None, gt=0.0, le=1.0,
            description="리스크 가드: 단일 포지션 손절률 — 초과 시 강제 청산 (M5 S14).",
        ),
    ) -> dict:
        """페어 백테스트를 실행하고 결과를 반환한다.

        WHY: 조립 루트(어댑터 레이어)에서 trading_signal 과 backtest
             두 L3 모듈을 결합한다. L1→L3 직접 import 는 금지이나
             이 파일은 인바운드 어댑터(조립 루트)이므로 허용된다.
        """
        # 1. 두 종목의 가격 시계열 로드 — Market 없이 symbol 만 받으므로
        #    기존 더미 Market 으로 Ticker 를 생성하고, repository.load 를 호출한다.
        #    WHY: /backtest/pair 는 심플 심볼 식별자만 사용하므로 Market 은 내부 식별용.
        ticker_a, ticker_b = _resolve_tickers(a, b)

        series_a = repository.load(ticker_a)
        if series_a is None:
            raise HTTPException(status_code=404, detail=f"{a}: 가격 시계열 없음")

        series_b = repository.load(ticker_b)
        if series_b is None:
            raise HTTPException(status_code=404, detail=f"{b}: 가격 시계열 없음")

        # 2. 공통 날짜 교집합 가격 시계열 추출
        common_dates, prices_a, prices_b = _intersect_series(series_a, series_b)
        if len(common_dates) < lookback + 1:
            raise HTTPException(
                status_code=400,
                detail=f"교집합 길이({len(common_dates)})가 lookback({lookback})+1 보다 짧습니다.",
            )

        # 3. 타임스탬프 변환 (date → datetime UTC)
        timestamps = [
            datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            for d in common_dates
        ]

        # 4. PairTradingSignalSource 조립 → TradingSignal 생성
        pair = Pair(a=a, b=b)
        signal_config = PairSignalConfig(
            entry_threshold=entry,
            exit_threshold=exit_,
            lookback_window=lookback,
        )
        signal_source = PairTradingSignalSource(
            pairs=[pair],
            timestamps=timestamps,
            config=signal_config,
        )
        trading_signals = signal_source.generate({a: prices_a, b: prices_b})

        # 5. TradingSignal → backtest Signal 변환
        backtest_signals = [trading_signal_to_backtest_signal(ts) for ts in trading_signals]

        # 6. price_history 구성 — PriceBar 로 변환
        price_history = _build_price_history(a, b, timestamps, prices_a, prices_b)

        # 7. BacktestConfig 생성 — rfr 은 Sharpe 비율 분모에 사용되므로 Decimal 로 변환
        config = BacktestConfig(
            initial_capital=Decimal(str(initial)),
            fee_rate=Decimal(str(fee)),
            slippage_bps=Decimal(str(slippage)),
            risk_free_rate=Decimal(str(rfr)),
        )

        # 8. InMemoryBacktestEngine 실행 — 선택된 사이저 주입
        # WHY: 사이저는 RunBacktest 유스케이스가 관리한다(M3 S13).
        #      InMemoryBacktestEngine.sizer 파라미터로 전달해 RunBacktest 에 위임한다.
        #      max_position_weight/cash_buffer 는 equal_weight 선택 시에만 의미 있다.
        sizer_instance = _build_sizer(sizer, max_position_weight, cash_buffer)
        # WHY: 두 어댑터가 동일 세션 객체를 공유해 peak/daily 추적 일관성 유지.
        risk_session = _build_risk_session(
            risk_position_limit, risk_max_drawdown, risk_daily_loss, risk_stop_loss,
        )
        risk_filter = _build_risk_filter(
            risk_position_limit, risk_max_drawdown, risk_daily_loss, risk_session,
        )
        risk_advisor = _build_risk_exit_advisor(risk_stop_loss, risk_session)
        engine = InMemoryBacktestEngine(
            sizer=sizer_instance,
            entry_filter=risk_filter,
            exit_advisor=risk_advisor,
        )
        result = engine.run(backtest_signals, price_history, config)

        # 9. 응답 직렬화 — 사용된 설정을 echo 로 포함해 UI 가 실행 조건을 표시할 수 있게 한다
        config_echo = {
            "lookback": lookback,
            "entry": entry,
            "exit": exit_,
            "initial": initial,
            "fee": fee,
            "slippage": slippage,
            "rfr": rfr,
            "sizer": sizer,
            "max_position_weight": max_position_weight,
            "cash_buffer": cash_buffer,
            "risk_position_limit": risk_position_limit,
            "risk_max_drawdown": risk_max_drawdown,
            "risk_daily_loss": risk_daily_loss,
            "risk_stop_loss": risk_stop_loss,
        }
        return _serialize_backtest_result(a, b, result, trading_signals, config_echo)

    @app.get("/backtest/pair/{a}/{b}/walk-forward")
    def backtest_walk_forward_endpoint(
        a: str,
        b: str,
        lookback: int = Query(_BACKTEST_DEFAULT_LOOKBACK),
        entry: float = Query(_BACKTEST_DEFAULT_ENTRY),
        exit_: float = Query(_BACKTEST_DEFAULT_EXIT, alias="exit"),
        initial: float = Query(_BACKTEST_DEFAULT_INITIAL),
        fee: float = Query(_BACKTEST_DEFAULT_FEE),
        slippage: float = Query(_BACKTEST_DEFAULT_SLIPPAGE),
        rfr: float = Query(_BACKTEST_DEFAULT_RFR, ge=0.0, le=1.0),
        sizer: Literal["strength", "equal_weight", "score_weighted"] = Query(
            _SIZER_STRENGTH
        ),
        max_position_weight: float = Query(
            _BACKTEST_DEFAULT_MAX_POSITION_WEIGHT, gt=0.0, le=1.0
        ),
        cash_buffer: float = Query(
            _BACKTEST_DEFAULT_CASH_BUFFER, ge=0.0, lt=1.0
        ),
        split_ratio: float = Query(
            0.7,
            gt=0.0,
            lt=1.0,
            description="In-sample 구간 비율. 0.7 이면 앞 70% = IS, 나머지 30% = OOS.",
        ),
        risk_position_limit: float | None = Query(None, gt=0.0, le=1.0),
        risk_max_drawdown: float | None = Query(None, gt=0.0, le=1.0),
        risk_daily_loss: float | None = Query(None, gt=0.0, le=1.0),
        risk_stop_loss: float | None = Query(None, gt=0.0, le=1.0),
    ) -> dict:
        """페어 백테스트를 walk-forward 방식으로 2 구간 분할 실행한다.

        WHY: 인샘플(IS)로 가설을 학습하고 아웃오브샘플(OOS)에서 성능이 유지되는지
             분리 평가해 과최적화 여부를 탐지한다. 가장 단순한 단일 split 형태로,
             공통 타임라인을 split_ratio 지점에서 자른 뒤 동일 엔진을 두 번 실행한다.
        """
        ticker_a, ticker_b = _resolve_tickers(a, b)

        series_a = repository.load(ticker_a)
        if series_a is None:
            raise HTTPException(status_code=404, detail=f"{a}: 가격 시계열 없음")
        series_b = repository.load(ticker_b)
        if series_b is None:
            raise HTTPException(status_code=404, detail=f"{b}: 가격 시계열 없음")

        common_dates, prices_a, prices_b = _intersect_series(series_a, series_b)
        if len(common_dates) < lookback + 1:
            raise HTTPException(
                status_code=400,
                detail=f"교집합 길이({len(common_dates)})가 lookback({lookback})+1 보다 짧습니다.",
            )

        timestamps = [
            datetime(d.year, d.month, d.day, tzinfo=timezone.utc) for d in common_dates
        ]
        pair = Pair(a=a, b=b)
        signal_config = PairSignalConfig(
            entry_threshold=entry, exit_threshold=exit_, lookback_window=lookback,
        )
        signal_source = PairTradingSignalSource(
            pairs=[pair], timestamps=timestamps, config=signal_config,
        )
        trading_signals = signal_source.generate({a: prices_a, b: prices_b})
        backtest_signals = [trading_signal_to_backtest_signal(ts) for ts in trading_signals]
        price_history = _build_price_history(a, b, timestamps, prices_a, prices_b)
        config = BacktestConfig(
            initial_capital=Decimal(str(initial)),
            fee_rate=Decimal(str(fee)),
            slippage_bps=Decimal(str(slippage)),
            risk_free_rate=Decimal(str(rfr)),
        )
        sizer_instance = _build_sizer(sizer, max_position_weight, cash_buffer)

        # WHY: IS/OOS 는 독립 세션이므로 각자 별도 엔진·세션 상태를 가진다.
        def _make_engine():
            session = _build_risk_session(
                risk_position_limit, risk_max_drawdown, risk_daily_loss, risk_stop_loss,
            )
            return InMemoryBacktestEngine(
                sizer=sizer_instance,
                entry_filter=_build_risk_filter(
                    risk_position_limit, risk_max_drawdown, risk_daily_loss, session,
                ),
                exit_advisor=_build_risk_exit_advisor(risk_stop_loss, session),
            )

        # WHY: 타임스탬프 기준 split 지점 계산. 전체 구간의 split_ratio 지점에서
        #      before/after 로 나눈다. 신호 없는 구간은 빈 결과로 반환된다.
        split_index = max(1, int(len(timestamps) * split_ratio))
        if split_index >= len(timestamps):
            raise HTTPException(
                status_code=400,
                detail="split_ratio 가 너무 커서 OOS 구간이 비었습니다.",
            )
        split_ts = timestamps[split_index]

        is_signals = [s for s in backtest_signals if s.timestamp < split_ts]
        oos_signals = [s for s in backtest_signals if s.timestamp >= split_ts]
        is_trading = [ts for ts in trading_signals if ts.timestamp < split_ts]
        oos_trading = [ts for ts in trading_signals if ts.timestamp >= split_ts]

        is_result = _make_engine().run(is_signals, price_history, config)
        oos_result = _make_engine().run(oos_signals, price_history, config)

        config_echo = {
            "lookback": lookback, "entry": entry, "exit": exit_,
            "initial": initial, "fee": fee, "slippage": slippage,
            "rfr": rfr, "sizer": sizer,
            "max_position_weight": max_position_weight,
            "cash_buffer": cash_buffer, "split_ratio": split_ratio,
        }
        return {
            "pair": {"a": a, "b": b},
            "split": {
                "ratio": split_ratio,
                "timestamp": split_ts.isoformat(),
                "index": split_index,
            },
            "in_sample": _serialize_backtest_result(
                a, b, is_result, is_trading, config_echo
            ),
            "out_of_sample": _serialize_backtest_result(
                a, b, oos_result, oos_trading, config_echo
            ),
            "config": config_echo,
        }

    @app.get("/backtest/pair/{a}/{b}/walk-forward-kfold")
    def backtest_walk_forward_kfold_endpoint(
        a: str,
        b: str,
        lookback: int = Query(_BACKTEST_DEFAULT_LOOKBACK),
        entry: float = Query(_BACKTEST_DEFAULT_ENTRY),
        exit_: float = Query(_BACKTEST_DEFAULT_EXIT, alias="exit"),
        initial: float = Query(_BACKTEST_DEFAULT_INITIAL),
        fee: float = Query(_BACKTEST_DEFAULT_FEE),
        slippage: float = Query(_BACKTEST_DEFAULT_SLIPPAGE),
        rfr: float = Query(_BACKTEST_DEFAULT_RFR, ge=0.0, le=1.0),
        sizer: Literal["strength", "equal_weight", "score_weighted"] = Query(
            _SIZER_STRENGTH
        ),
        max_position_weight: float = Query(
            _BACKTEST_DEFAULT_MAX_POSITION_WEIGHT, gt=0.0, le=1.0
        ),
        cash_buffer: float = Query(
            _BACKTEST_DEFAULT_CASH_BUFFER, ge=0.0, lt=1.0
        ),
        folds: int = Query(
            3, ge=2, le=10,
            description="타임라인을 k 등분한 후 rolling 하게 k-1 개 폴드를 생성.",
        ),
        risk_position_limit: float | None = Query(None, gt=0.0, le=1.0),
        risk_max_drawdown: float | None = Query(None, gt=0.0, le=1.0),
        risk_daily_loss: float | None = Query(None, gt=0.0, le=1.0),
        risk_stop_loss: float | None = Query(None, gt=0.0, le=1.0),
    ) -> dict:
        """Walk-forward 다중 폴드: 타임라인을 k 등분하고 인접 segment 쌍으로 k-1 폴드 생성.

        WHY: 단일 split 대비 과적합 탐지력을 높인다. fold i = (IS=seg_i, OOS=seg_{i+1})
             로 정의하며 각 폴드의 IS/OOS 지표를 평균해 변동성을 가늠한다.
        """
        ticker_a, ticker_b = _resolve_tickers(a, b)
        series_a = repository.load(ticker_a)
        if series_a is None:
            raise HTTPException(status_code=404, detail=f"{a}: 가격 시계열 없음")
        series_b = repository.load(ticker_b)
        if series_b is None:
            raise HTTPException(status_code=404, detail=f"{b}: 가격 시계열 없음")

        common_dates, prices_a, prices_b = _intersect_series(series_a, series_b)
        if len(common_dates) < lookback + folds + 1:
            raise HTTPException(
                status_code=400,
                detail=f"교집합 길이({len(common_dates)})가 lookback({lookback})+folds({folds})+1 보다 짧습니다.",
            )

        timestamps = [
            datetime(d.year, d.month, d.day, tzinfo=timezone.utc) for d in common_dates
        ]
        pair = Pair(a=a, b=b)
        signal_config = PairSignalConfig(
            entry_threshold=entry, exit_threshold=exit_, lookback_window=lookback,
        )
        signal_source = PairTradingSignalSource(
            pairs=[pair], timestamps=timestamps, config=signal_config,
        )
        trading_signals = signal_source.generate({a: prices_a, b: prices_b})
        backtest_signals = [trading_signal_to_backtest_signal(ts) for ts in trading_signals]
        price_history = _build_price_history(a, b, timestamps, prices_a, prices_b)
        config = BacktestConfig(
            initial_capital=Decimal(str(initial)),
            fee_rate=Decimal(str(fee)),
            slippage_bps=Decimal(str(slippage)),
            risk_free_rate=Decimal(str(rfr)),
        )
        sizer_instance = _build_sizer(sizer, max_position_weight, cash_buffer)

        def _make_engine():
            session = _build_risk_session(
                risk_position_limit, risk_max_drawdown, risk_daily_loss, risk_stop_loss,
            )
            return InMemoryBacktestEngine(
                sizer=sizer_instance,
                entry_filter=_build_risk_filter(
                    risk_position_limit, risk_max_drawdown, risk_daily_loss, session,
                ),
                exit_advisor=_build_risk_exit_advisor(risk_stop_loss, session),
            )

        # WHY: k 등분 경계 인덱스. int 캐스팅으로 마지막 segment 가 약간 길어질 수 있음.
        n = len(timestamps)
        boundaries = [int(n * i / folds) for i in range(folds + 1)]
        boundaries[-1] = n

        fold_results: list[dict] = []
        is_returns: list[float] = []
        oos_returns: list[float] = []
        is_sharpes: list[float] = []
        oos_sharpes: list[float] = []

        for i in range(folds - 1):
            is_start, is_end = boundaries[i], boundaries[i + 1]
            oos_start, oos_end = boundaries[i + 1], boundaries[i + 2]
            is_lo, is_hi = timestamps[is_start], timestamps[is_end - 1]
            oos_lo, oos_hi = timestamps[oos_start], timestamps[oos_end - 1]

            is_sigs = [s for s in backtest_signals if is_lo <= s.timestamp <= is_hi]
            oos_sigs = [s for s in backtest_signals if oos_lo <= s.timestamp <= oos_hi]
            is_trading = [t for t in trading_signals if is_lo <= t.timestamp <= is_hi]
            oos_trading = [t for t in trading_signals if oos_lo <= t.timestamp <= oos_hi]

            # WHY: 폴드 간 세션 상태 누출을 막기 위해 폴드마다 새 엔진 생성.
            is_result = _make_engine().run(is_sigs, price_history, config)
            oos_result = _make_engine().run(oos_sigs, price_history, config)

            fold_results.append({
                "fold": i,
                "in_sample": _serialize_backtest_result(a, b, is_result, is_trading, {}),
                "out_of_sample": _serialize_backtest_result(a, b, oos_result, oos_trading, {}),
            })
            is_returns.append(float(is_result.metrics.total_return))
            oos_returns.append(float(oos_result.metrics.total_return))
            is_sharpes.append(is_result.metrics.sharpe)
            oos_sharpes.append(oos_result.metrics.sharpe)

        def _avg(xs: list[float]) -> float:
            return sum(xs) / len(xs) if xs else 0.0

        return {
            "pair": {"a": a, "b": b},
            "folds": folds,
            "fold_count": len(fold_results),
            "aggregate": {
                "avg_is_total_return": _avg(is_returns),
                "avg_oos_total_return": _avg(oos_returns),
                "avg_is_sharpe": _avg(is_sharpes),
                "avg_oos_sharpe": _avg(oos_sharpes),
            },
            "results": fold_results,
        }

    @app.post("/backtest/batch")
    def backtest_batch_endpoint(req: BatchBacktestRequest) -> dict:
        """여러 페어를 동일 파라미터로 백테스트하고 지표를 집계한다.

        WHY: 단일 페어 백테스트를 반복 호출하지 않고도 여러 가설을
             한 번에 비교할 수 있게 한다. 집계는 평균 total_return / sharpe
             로 단순 요약만 제공하며 각 페어별 전체 결과도 함께 반환한다.
             실패한 페어는 error 필드로 보고하고 집계에서 제외한다.
        """
        config = BacktestConfig(
            initial_capital=Decimal(str(req.initial)),
            fee_rate=Decimal(str(req.fee)),
            slippage_bps=Decimal(str(req.slippage)),
            risk_free_rate=Decimal(str(req.rfr)),
        )
        sizer_instance = _build_sizer(req.sizer, req.max_position_weight, req.cash_buffer)
        engine = InMemoryBacktestEngine(sizer=sizer_instance)
        signal_config = PairSignalConfig(
            entry_threshold=req.entry,
            exit_threshold=req.exit,
            lookback_window=req.lookback,
        )

        per_pair: list[dict] = []
        success_returns: list[float] = []
        success_sharpes: list[float] = []

        for pair_ref in req.pairs:
            try:
                result = _run_single_pair_backtest(
                    pair_ref.a, pair_ref.b, repository, engine, config,
                    signal_config, req.lookback,
                )
            except HTTPException as exc:
                per_pair.append({
                    "pair": {"a": pair_ref.a, "b": pair_ref.b},
                    "error": exc.detail,
                })
                continue

            metrics = result.metrics
            per_pair.append({
                "pair": {"a": pair_ref.a, "b": pair_ref.b},
                "metrics": {
                    "total_return": float(metrics.total_return),
                    "sharpe": metrics.sharpe,
                    "sortino": metrics.sortino,
                    "calmar": metrics.calmar,
                    "max_drawdown": float(metrics.max_drawdown),
                    "win_rate": metrics.win_rate,
                },
                "trade_count": len(result.trades),
            })
            success_returns.append(float(metrics.total_return))
            success_sharpes.append(metrics.sharpe)

        aggregate: dict = {
            "pair_count": len(req.pairs),
            "success_count": len(success_returns),
        }
        if success_returns:
            aggregate["avg_total_return"] = sum(success_returns) / len(success_returns)
            aggregate["avg_sharpe"] = sum(success_sharpes) / len(success_sharpes)
        return {"aggregate": aggregate, "results": per_pair}

    @app.post("/portfolio/compute", response_model=ComputeWeightsResponse)
    def compute_weights_endpoint(req: ComputeWeightsRequest) -> ComputeWeightsResponse:
        """시그널과 전략을 받아 목표 비중을 계산하고 반환한다.

        WHY: ComputeTargetWeights 유스케이스를 HTTP 로 노출하는 얇은 어댑터.
             strategy 문자열로 전략 구현체를 선택하고, 도메인 ValueError 는
             400 으로 변환한다. 직렬화·역직렬화만 담당하며 비즈니스 로직을 포함하지 않는다.
        """
        try:
            result_weights = _execute_compute_weights(req)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return ComputeWeightsResponse(
            weights=[
                TargetWeightResponse(symbol=w.symbol, weight=float(w.weight))
                for w in result_weights
            ]
        )

    @app.post("/portfolio/rebalance", response_model=RebalanceResponse)
    def rebalance_endpoint(req: RebalanceRequest) -> RebalanceResponse:
        """현재 포지션과 목표 비중을 받아 리밸런싱 주문 계획을 반환한다.

        WHY: PlanRebalance 유스케이스를 HTTP 로 노출하는 얇은 어댑터.
             도메인 ValueError 는 400 으로 변환하고, 직렬화만 담당한다.
        """
        if req.total_equity <= 0:
            raise HTTPException(status_code=400, detail="total_equity 는 양수여야 합니다.")

        try:
            current, targets = _to_domain_inputs(req)
            plan = _execute_plan_rebalance(current, targets, req)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return RebalanceResponse(
            intents=[
                OrderIntentResponse(
                    symbol=intent.symbol,
                    delta_weight=float(intent.delta_weight),
                    side=intent.side,
                )
                for intent in plan.intents
            ]
        )

    return app


def _run_single_pair_backtest(
    a: str,
    b: str,
    repository: PriceRepository,
    engine: InMemoryBacktestEngine,
    config: BacktestConfig,
    signal_config: PairSignalConfig,
    lookback: int,
):
    """단일 페어의 신호 생성 + 백테스트 엔진 실행을 수행한다.

    WHY: /backtest/pair 와 /backtest/batch 가 공유하는 로직을 한 곳에 모은다.
         실패 경로는 HTTPException 으로 통일해 호출자가 일관되게 처리한다.
    """
    ticker_a, ticker_b = _resolve_tickers(a, b)
    series_a = repository.load(ticker_a)
    if series_a is None:
        raise HTTPException(status_code=404, detail=f"{a}: 가격 시계열 없음")
    series_b = repository.load(ticker_b)
    if series_b is None:
        raise HTTPException(status_code=404, detail=f"{b}: 가격 시계열 없음")

    common_dates, prices_a, prices_b = _intersect_series(series_a, series_b)
    if len(common_dates) < lookback + 1:
        raise HTTPException(
            status_code=400,
            detail=f"교집합 길이({len(common_dates)})가 lookback({lookback})+1 보다 짧습니다.",
        )

    timestamps = [
        datetime(d.year, d.month, d.day, tzinfo=timezone.utc) for d in common_dates
    ]
    pair = Pair(a=a, b=b)
    signal_source = PairTradingSignalSource(
        pairs=[pair], timestamps=timestamps, config=signal_config,
    )
    trading_signals = signal_source.generate({a: prices_a, b: prices_b})
    backtest_signals = [trading_signal_to_backtest_signal(ts) for ts in trading_signals]
    price_history = _build_price_history(a, b, timestamps, prices_a, prices_b)
    return engine.run(backtest_signals, price_history, config)


def _build_risk_session(
    position_limit: float | None,
    max_drawdown: float | None,
    daily_loss: float | None,
    stop_loss: float | None,
):
    """어떤 리스크 가드든 활성이면 공유 RiskSessionState 를 반환한다.

    WHY: EntryFilter 와 ExitAdvisor 가 동일 세션 객체를 공유해야 peak/daily
         추적이 단일 진실원으로 동작한다 (review followup).
    """
    if all(v is None for v in (position_limit, max_drawdown, daily_loss, stop_loss)):
        return None
    from backtest.adapters.outbound.risk_session_state import RiskSessionState
    return RiskSessionState()


def _build_risk_filter(
    position_limit: float | None,
    max_drawdown: float | None,
    daily_loss: float | None,
    session_state=None,
):
    """리스크 가드 파라미터를 받아 RiskEntryFilter 를 조립한다.

    WHY: 모든 파라미터가 None 이면 None 을 반환해 RunBacktest 기본 동작을 유지한다.
         하나라도 지정되면 해당 가드만 체인에 포함한다 (선택적 활성).
    """
    if position_limit is None and max_drawdown is None and daily_loss is None:
        return None
    from backtest.adapters.outbound.risk_entry_filter import RiskEntryFilter
    from risk.adapters.outbound import (
        DailyLossLimitGuard,
        DrawdownCircuitBreaker,
        PositionLimitGuard,
    )
    guards = []
    if position_limit is not None:
        guards.append(PositionLimitGuard(max_weight=Decimal(str(position_limit))))
    if max_drawdown is not None:
        guards.append(DrawdownCircuitBreaker(max_drawdown=Decimal(str(max_drawdown))))
    if daily_loss is not None:
        guards.append(DailyLossLimitGuard(max_daily_loss=Decimal(str(daily_loss))))
    return RiskEntryFilter(guards=guards, session_state=session_state)


def _build_risk_exit_advisor(stop_loss: float | None, session_state=None):
    """stop_loss 가 지정되면 RiskExitAdvisor(StopLossGuard) 를 조립한다 (M5 S14).

    WHY: 진입 차단(EntryFilter) 만으로는 보유 포지션을 강제 청산할 수 없으므로
         별도 ExitAdvisor 경로로 StopLossGuard 의 ForceClose 를 EXIT 로 변환한다.
    """
    if stop_loss is None:
        return None
    from backtest.adapters.outbound.risk_exit_advisor import RiskExitAdvisor
    from risk.adapters.outbound import StopLossGuard
    return RiskExitAdvisor(
        guards=[StopLossGuard(max_loss_pct=Decimal(str(stop_loss)))],
        session_state=session_state,
    )


def _build_sizer(
    sizer_name: str,
    max_position_weight: float = _BACKTEST_DEFAULT_MAX_POSITION_WEIGHT,
    cash_buffer: float = _BACKTEST_DEFAULT_CASH_BUFFER,
) -> PositionSizer | None:
    """사이저 이름으로 PositionSizer 인스턴스를 생성한다.

    WHY: 조립 루트(어댑터)에서만 L3 모듈 간 조립을 허용한다.
         equal_weight/score_weighted 선택 시 portfolio L3 모듈을 import 해 조립하고,
         strength(기본값)는 None 을 반환해 InMemoryTradeExecutor 기본값을 사용한다.
         import 를 함수 내부로 한정해 strength 선택 시 portfolio 의존을 제거한다.
         max_position_weight/cash_buffer 는 portfolio 사이저 선택 시에만 의미 있으며
         strength 에서는 무시된다 (경고 로그 없음 — 클라이언트 책임).

    Args:
        sizer_name: "strength", "equal_weight", 또는 "score_weighted"
        max_position_weight: 최대 포지션 비중 (0~1). portfolio 사이저 전용.
        cash_buffer: 현금 버퍼 비율 (0~1). portfolio 사이저 전용.

    Returns:
        PositionSizer 인스턴스, 또는 기본값 사용 시 None
    """
    if sizer_name == _SIZER_EQUAL_WEIGHT:
        from portfolio.adapters.outbound.equal_weight_strategy import EqualWeightStrategy
        from portfolio.domain.constraints import PortfolioConstraints
        from backtest.adapters.outbound.portfolio_position_sizer import PortfolioPositionSizer
        constraints = PortfolioConstraints(
            max_position_weight=Decimal(str(max_position_weight)),
            cash_buffer=Decimal(str(cash_buffer)),
        )
        return PortfolioPositionSizer(EqualWeightStrategy(), constraints)
    if sizer_name == _SIZER_SCORE_WEIGHTED:
        from portfolio.adapters.outbound.score_weighted_strategy import ScoreWeightedStrategy
        from portfolio.domain.constraints import PortfolioConstraints
        from backtest.adapters.outbound.portfolio_position_sizer import PortfolioPositionSizer
        constraints = PortfolioConstraints(
            max_position_weight=Decimal(str(max_position_weight)),
            cash_buffer=Decimal(str(cash_buffer)),
        )
        return PortfolioPositionSizer(ScoreWeightedStrategy(), constraints)
    # strength: 기본 StrengthPositionSizer 사용 — None 반환으로 기존 동작 유지
    return None


def _resolve_tickers(a: str, b: str) -> tuple[Ticker, Ticker]:
    """심볼 문자열로부터 Ticker 를 생성한다.

    WHY: /backtest/pair 는 마켓 구분 없이 심볼만 받는다.
         기본 마켓(KRX)으로 Ticker 를 생성해 repository.load 에 넘긴다.
         실제 저장소가 심볼 기반으로 검색하므로 Market 은 식별용으로만 사용된다.
    """
    default_market = Market("KRX")
    return Ticker(default_market, a), Ticker(default_market, b)


def _build_price_history(
    ticker_a: str,
    ticker_b: str,
    timestamps: list[datetime],
    prices_a: list[float],
    prices_b: list[float],
) -> dict[str, list[PriceBar]]:
    """(ticker, timestamp) → PriceBar 매핑을 위한 price_history 딕셔너리를 생성한다.

    WHY: InMemoryBacktestEngine 은 PriceBar.close 를 사용해 mark-to-market 을 계산한다.
         OHLCV 는 모두 adj_close 로 근사한다 (일별 데이터의 단순화).
    """
    bars_a = [_make_price_bar(ticker_a, ts, price) for ts, price in zip(timestamps, prices_a)]
    bars_b = [_make_price_bar(ticker_b, ts, price) for ts, price in zip(timestamps, prices_b)]
    return {ticker_a: bars_a, ticker_b: bars_b}


def _make_price_bar(ticker: str, timestamp: datetime, price: float) -> PriceBar:
    """단일 adj_close 가격으로 PriceBar 를 생성한다.

    WHY: 일별 OHLCV 가 없으므로 OHLCV 전체를 adj_close 로 설정한다.
         volume 은 0 으로 설정해 불변식을 충족한다.
    """
    close = Decimal(str(price))
    return PriceBar(
        timestamp=timestamp,
        ticker=ticker,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=Decimal("0"),
    )


def _serialize_backtest_result(
    a: str,
    b: str,
    result: object,
    trading_signals: list,
    config_echo: dict,
) -> dict:
    """BacktestResult 를 JSON 직렬화 가능한 딕셔너리로 변환한다.

    WHY: BacktestResult 는 도메인 값 객체라 datetime/Decimal 을 포함하므로
         HTTP 응답 전 직렬화 변환이 필요하다.
    """
    from trading_signal.domain.side import Side as TSSide

    metrics = result.metrics
    trades = [
        {
            "ticker": t.ticker,
            "entry_time": t.entry_time.isoformat(),
            "exit_time": t.exit_time.isoformat(),
            "pnl": float(t.pnl),
        }
        for t in result.trades
    ]
    equity_curve = [
        {"timestamp": ts.isoformat(), "value": float(val)}
        for ts, val in result.equity_curve
    ]

    long_count = sum(1 for s in trading_signals if s.side == TSSide.LONG)
    short_count = sum(1 for s in trading_signals if s.side == TSSide.SHORT)
    exit_count = sum(1 for s in trading_signals if s.side == TSSide.EXIT)

    return {
        "pair": {"a": a, "b": b},
        "metrics": {
            "total_return": float(metrics.total_return),
            "sharpe": metrics.sharpe,
            "max_drawdown": float(metrics.max_drawdown),
            "win_rate": metrics.win_rate,
            "sortino": metrics.sortino,
            "calmar": metrics.calmar,
        },
        "trades": trades,
        "equity_curve": equity_curve,
        "signals_count": {"long": long_count, "short": short_count, "exit": exit_count},
        "config": config_echo,
    }


def _execute_query(
    find_similar: FindSimilarTickers,
    query: FindSimilarQuery,
    target: Ticker,
    weights: SimilarityWeights,
    repository: PriceRepository | None = None,
) -> dict:
    """유스케이스를 실행하고 HTTP 에러로 변환한다.

    WHY: ValueError 를 HTTP 상태 코드로 매핑하는 책임을 분리해
         엔드포인트 함수의 가독성을 유지한다.

    Args:
        find_similar: 유사 종목 탐색 유스케이스 인스턴스
        query: 탐색 쿼리 값 객체
        target: 대상 종목 티커
        weights: 응답에 포함할 가중치 값 객체
    """
    try:
        results = find_similar.execute(query)
    except ValueError as exc:
        if _ERR_SERIES_MISSING in str(exc):
            # WHY: 시계열 데이터가 없으면 비교 대상이 없어 빈 결과를 반환한다.
            #      데이터 부재는 클라이언트 오류가 아니라 데이터 미수집 상태이다.
            results = []
        else:
            _raise_http_error(exc)

    # WHY: 2D 시각화(유사도×변동성 스캐터) 를 위해 각 결과 티커의 연환산 변동성을
    #      추가 지표로 계산한다. 쿼리 타겟도 함께 계산해 프런트가 기준점으로 사용.
    vol_map: dict[str, float] = {}
    if repository is not None:
        tickers_to_quote = [target] + [r.ticker for r in results]
        for tk in tickers_to_quote:
            key = str(tk)
            if key in vol_map:
                continue
            vol = _annualized_volatility(repository, tk)
            if vol is not None:
                vol_map[key] = vol

    return {
        "target": str(target),
        "target_volatility": vol_map.get(str(target)),
        "weights": {"w1": weights.w1, "w2": weights.w2, "w3": weights.w3},
        "results": [
            {
                "ticker": str(r.ticker),
                "score": r.score,
                "volatility": vol_map.get(str(r.ticker)),
            }
            for r in results
        ],
    }


# WHY: 로그수익률 표본표준편차 × √252 → 연환산 변동성. 252 = KRX/NASDAQ 공통
#      거래일 연간 근사. 표본 부족(<2) 이면 None 반환해 프런트가 결측 처리.
_TRADING_DAYS_PER_YEAR = 252
_MIN_RETURNS_FOR_VOL = 2


def _annualized_volatility(
    repository: PriceRepository, ticker: Ticker
) -> float | None:
    """단일 티커의 연환산 로그수익률 변동성을 계산한다."""
    try:
        series = repository.load(ticker)
    except Exception:
        return None
    if series is None:
        return None
    prices = [float(p.value) for _, p in series.prices]
    if len(prices) < _MIN_RETURNS_FOR_VOL + 1:
        return None
    returns = _to_log_returns(prices)
    if len(returns) < _MIN_RETURNS_FOR_VOL:
        return None
    mean = sum(returns) / len(returns)
    var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    return math.sqrt(var) * math.sqrt(_TRADING_DAYS_PER_YEAR)


def _raise_http_error(exc: ValueError) -> None:
    """ValueError 메시지에 따라 적절한 HTTPException 을 발생시킨다.

    WHY: 유니버스 부재는 클라이언트가 요청한 리소스가 없는 상황이므로 404,
         그 외 ValueError 는 잘못된 입력(400) 으로 구분한다.
    """
    if _ERR_NOT_IN_UNIVERSE in str(exc):
        raise HTTPException(status_code=404, detail=str(exc))
    raise HTTPException(status_code=400, detail=str(exc))


def _intersect_series(
    series_a: object,
    series_b: object,
) -> tuple[list[date], list[float], list[float]]:
    """두 PriceSeries 의 공통 날짜(교집합)와 해당 adj_close 를 반환한다.

    WHY: 두 종목의 거래일이 다를 수 있으므로 공통 날짜를 기준으로 정렬해야만
         일대일 수익률 비교가 가능하다. 교집합 기준 정렬로 날짜 동기화를 보장한다.

    Returns:
        (공통 날짜 정렬 리스트, a의 가격 리스트, b의 가격 리스트)
    """
    dict_a = {d: float(p.value) for d, p in series_a.prices}
    dict_b = {d: float(p.value) for d, p in series_b.prices}
    common = sorted(dict_a.keys() & dict_b.keys())
    prices_a = [dict_a[d] for d in common]
    prices_b = [dict_b[d] for d in common]
    return common, prices_a, prices_b


def _to_log_returns(prices: list[float]) -> list[float]:
    """연속 가격 리스트로부터 로그수익률 리스트를 계산한다."""
    return [math.log(prices[i] / prices[i - 1]) for i in range(1, len(prices))]


def _to_domain_inputs(
    req: RebalanceRequest,
) -> tuple[list, list]:
    """요청 DTO 를 도메인 값 객체 목록으로 변환한다.

    WHY: float → Decimal 변환 시 str 경유로 부동소수점 오차를 제거한다.
         도메인 불변식(symbol 비공백, weight 범위) 위반 시 ValueError 를 발생시켜
         엔드포인트에서 400 으로 변환하도록 위임한다.
    """
    from portfolio.domain.position import CurrentPosition
    from portfolio.domain.weight import TargetWeight

    current = [
        CurrentPosition(
            symbol=p.symbol,
            quantity=Decimal(str(p.quantity)),
            market_value=Decimal(str(p.market_value)),
        )
        for p in req.current_positions
    ]
    targets = [
        TargetWeight(symbol=t.symbol, weight=Decimal(str(t.weight)))
        for t in req.target_weights
    ]
    return current, targets


def _execute_plan_rebalance(
    current: list,
    targets: list,
    req: RebalanceRequest,
) -> object:
    """PlanRebalance 유스케이스를 실행하고 RebalancePlan 을 반환한다.

    WHY: import 를 함수 내부로 한정해 portfolio 의존이 엔드포인트 정의와
         분리되도록 한다. 사이드 이펙트 없는 순수 호출 래퍼 역할.
    """
    from portfolio.application.use_cases.plan_rebalance import PlanRebalance
    from portfolio.domain.constraints import PortfolioConstraints

    constraints = None
    if req.max_position_weight is not None or req.cash_buffer is not None:
        constraints = PortfolioConstraints(
            max_position_weight=Decimal(str(req.max_position_weight))
            if req.max_position_weight is not None
            else Decimal("1"),
            cash_buffer=Decimal(str(req.cash_buffer))
            if req.cash_buffer is not None
            else Decimal("0"),
        )
    use_case = PlanRebalance(
        min_trade_weight=Decimal(str(req.min_trade_weight)),
        constraints=constraints,
    )
    return use_case.execute(current, targets, Decimal(str(req.total_equity)))


def _execute_compute_weights(req: ComputeWeightsRequest) -> tuple:
    """ComputeTargetWeights 유스케이스를 조립하고 실행한다.

    WHY: import 를 함수 내부로 한정해 portfolio 의존이 엔드포인트 정의와
         분리되도록 한다. strategy 문자열에 따라 올바른 전략 구현체를 선택한다.
         float → Decimal 변환 시 str 경유로 부동소수점 오차를 제거한다.

    Args:
        req: ComputeWeightsRequest DTO

    Returns:
        tuple[TargetWeight, ...] — 목표 비중 튜플
    """
    from portfolio.adapters.outbound.equal_weight_strategy import EqualWeightStrategy
    from portfolio.adapters.outbound.score_weighted_strategy import ScoreWeightedStrategy
    from portfolio.application.ports.weighting_strategy import SignalInput
    from portfolio.application.use_cases.compute_target_weights import ComputeTargetWeights
    from portfolio.domain.constraints import PortfolioConstraints

    strategy_instance = (
        EqualWeightStrategy()
        if req.strategy == _STRATEGY_EQUAL_WEIGHT
        else ScoreWeightedStrategy()
    )
    constraints = PortfolioConstraints(
        max_position_weight=Decimal(str(req.max_position_weight)),
        cash_buffer=Decimal(str(req.cash_buffer)),
    )
    signals = [
        SignalInput(symbol=s.symbol, score=Decimal(str(s.score)))
        for s in req.signals
    ]
    use_case = ComputeTargetWeights(strategy=strategy_instance)
    return use_case.execute(signals, constraints)


def _compute_rolling_corr(
    returns_a: list[float],
    returns_b: list[float],
    window: int,
) -> list[float | None]:
    """rolling window Pearson 상관계수 배열을 계산한다.

    WHY: window 미만 구간은 데이터가 부족해 상관계수를 계산할 수 없으므로
         null 로 채워 클라이언트 차트 x축이 log_returns 와 정확히 일치하도록 한다.

    Returns:
        길이 == len(returns_a) 인 리스트. 처음 window-1 개는 None, 이후는 float.
    """
    result: list[float | None] = []
    for i in range(len(returns_a)):
        if i + 1 < window:
            result.append(None)
        else:
            slice_a = returns_a[i - window + 1 : i + 1]
            slice_b = returns_b[i - window + 1 : i + 1]
            corr = pearson_correlation(slice_a, slice_b)
            result.append(corr.value)
    return result
