# portfolio (L3 활성화)

**상태**: L3 엄격도 활성화 (ADR-004, 2026-04-07)

## 책임

포지션 사이징과 리밸런싱 계획 생성만 담당한다.

| 담당 | 미담당 |
|---|---|
| 목표 비중 계산 (`ComputeTargetWeights`) | 실거래 주문 실행 (trading 도메인) |
| 리밸런싱 계획 생성 (`PlanRebalance`) | 리스크 한도 검증 (risk 도메인) |
| 가중치 전략 포트 (`WeightingStrategy`) | 백테스트 성과 계산 (backtest 도메인) |

## 패키지 구조

```
portfolio/
├── domain/
│   ├── weight.py          # TargetWeight VO
│   ├── position.py        # CurrentPosition VO
│   ├── constraints.py     # PortfolioConstraints VO
│   ├── rebalance_plan.py  # OrderIntent + RebalancePlan VO
│   └── errors.py          # WeightSumError, ConstraintViolation
├── application/
│   └── ports/
│       └── weighting_strategy.py  # WeightingStrategy Protocol + SignalInput DTO
│   └── use_cases/
│       ├── compute_target_weights.py  # ComputeTargetWeights 유스케이스
│       └── plan_rebalance.py          # PlanRebalance 유스케이스
└── adapters/
    └── outbound/
        └── equal_weight_strategy.py  # EqualWeightStrategy (M3 한정)
```

## L3 엄격도 규칙

- 커버리지 90%+ 의무
- 단일 에이전트 구현 금지 (`/develop` 다중 에이전트 파이프라인 사용)
- `pandas`, `numpy` 를 `domain/`, `application/` 에서 직접 import 금지
- L2 패키지(`market_data`, `universe`, `similarity`)에서 이 패키지 import 금지
- import-linter: `portfolio hexagonal layers` + `portfolio domain/application purity` 계약 통과 필수

## 의존 방향

```
adapters.outbound → application.ports → domain
adapters.outbound → application.use_cases → application.ports → domain
```

## 관련 ADR

- [ADR-001](../../docs/adr/ADR-001-domain-levels.md) — 도메인 엄격도 레벨
- [ADR-004](../../docs/adr/ADR-004-portfolio-l3-activation.md) — portfolio L3 활성화 결정
- [ADR-005](../../docs/adr/ADR-005-l3-horizontal-dependency.md) — L3 패키지 간 수평 의존 정책 (backtest→portfolio 어댑터 레이어 전용)
