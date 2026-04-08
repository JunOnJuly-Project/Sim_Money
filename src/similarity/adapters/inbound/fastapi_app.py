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
from typing import Callable, Literal

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
_BACKTEST_DEFAULT_INITIAL = 10_000.0
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


class ComputeWeightsResponse(BaseModel):
    """POST /portfolio/compute 응답 바디."""

    weights: list[TargetWeightResponse]


def create_app(
    repository: PriceRepository,
    universe_source: UniverseSource,
    strategy_factory: Callable[[SimilarityWeights], SimilarityStrategy],
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
    app = FastAPI()

    @app.get("/health")
    def health() -> dict:
        """로드밸런서 헬스 프로브용 엔드포인트."""
        return {"status": "ok"}

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
    ) -> dict:
        """유사 종목 목록을 반환한다."""
        try:
            weights = SimilarityWeights(w1, w2, w3)
            strategy = strategy_factory(weights)
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
        return _execute_query(find_similar, query, target, weights)

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
        engine = InMemoryBacktestEngine(sizer=sizer_instance)
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
        }
        return _serialize_backtest_result(a, b, result, trading_signals, config_echo)

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

    return {
        "target": str(target),
        "weights": {"w1": weights.w1, "w2": weights.w2, "w3": weights.w3},
        "results": [{"ticker": str(r.ticker), "score": r.score} for r in results],
    }


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

    use_case = PlanRebalance(min_trade_weight=Decimal(str(req.min_trade_weight)))
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
