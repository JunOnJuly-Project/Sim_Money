# ADR-002: 공식은 Strategy 패턴으로 교체 가능, MVP 는 WeightedSum 1개

- 상태: Accepted
- 날짜: 2026-04-07
- 관련: [ADR-000](ADR-000-endgame.md), [ADR-001](ADR-001-domain-levels.md)

## 컨텍스트

"두 종목이 비슷하다" 의 정의는 하나가 아니다. 델파이 3라운드 결과
정확한 공식은 Phase 2+ 문제이며, MVP 는 **사용자(본인)가 슬라이더로 공식을 탐색하는 도구**
로 접근하는 것이 합리적이다. 후보 공식은 많다:

- Pearson, Spearman, Kendall 상관
- Mantegna 거리 √(2(1−ρ))
- Engle-Granger 공적분
- DTW (dtaidistance)
- 리드-래그 시차 상관
- DCC-GARCH 동적 상관

이들을 전부 MVP 에 넣는 것은 스코프 크립이며, 하나만 하드코딩하는 것은
Phase 2+ 확장성을 파괴한다.

## 결정

### Strategy 패턴 채택

```
similarity/
├── ports/
│   └── similarity_strategy.py        # 인터페이스
├── strategies/
│   └── weighted_sum.py               # M1 유일 구현
└── model/
    ├── score.py
    └── correlation_matrix.py
```

- **포트**: `SimilarityStrategy.compute(a: Return, b: Return, params: dict) -> Score`
- **M1 구현**: `WeightedSumStrategy` 1개 (아래 공식)
- **파라미터 전달**: config dict. UI 슬라이더는 전략 파라미터를 일반적 key-value 로 노출하므로,
  새 전략 추가 시 UI 재작성 없이 슬라이더 메타데이터만 갱신하면 된다.
- **Phase 2+ 확장**: `SpearmanStrategy`, `CointegrationStrategy`, `DTWStrategy`, `DCCGARCHStrategy`
  모두 같은 인터페이스의 추가 구현으로 도입.

### MVP 공식 (WeightedSumStrategy)

```
score(A,B) = sign(ρ_p) · ( w₁·|ρ_p| + w₂·shape + w₃·stability )

ρ_p       = pearson(logret_A, logret_B)
shape     = |cosine_similarity(logret_A, logret_B)|          # M1 단순화
stability = clip(1 − 2·std(rolling_corr_W), 0, 1)            # M1 기본 W=20, N<W 면 0

기본 가중치: w₁/w₂/w₃ = 0.5/0.3/0.2 (합=1 엄격 검증, 허용오차 1e-6)
필터: |ρ_p| ≥ 0.1, TopK(ρ_p,150) ∪ BottomK(ρ_p,150)
전처리: N≥252, σ≥1e-6, NaN>5% 제외, NaN/Inf 가드, sign(0)→+1
```

#### M1 단순화 사유 (갱신: 2026-04-07)
- `shape` 를 코사인 유사도로 치환: M1 범위에서는 "벡터 방향성" 이 직관적이고
  O(N) 비용으로 구현 가능. 원안(rolling std) 은 stability 와 측정 축이 겹쳐 중복 리스크가 있었음.
- `stability` 윈도우를 60 → 20 으로 축소: M1 골든 데이터셋(N≈252) 에서 60 은 관측수 대비 과도.
  Phase 2 에서 백테스트 기반으로 재조정 예정.
- 이 단순화는 Phase 2 재평가 대상이며, 별도 전략(`CosineShapeStrategy` 등) 으로 분리 가능.

## 결과

### 긍정적
- Phase 2+ 에서 공식 교체가 UI 재작성 없이 가능.
- MVP 는 단일 전략만 구현하므로 스코프 보호.
- 골든 테스트가 전략 단위로 고정된다.

### 부정적 / 트레이드오프
- Strategy 인터페이스 오버헤드가 M1 부터 존재.
- config dict 기반 파라미터는 타입 안전성이 약하다 (Phase 2 에 Pydantic 전환 고려).

### 알려진 한계 (UI 고지 + `docs/limitations.md` 에도 기록)

1. **상관관계 ≠ 공적분**: mean-reversion 보장 없음. 투자 판단 근거 아님.
2. **체제변화(regime change) 취약**: 과거 상관이 미래를 보장하지 않음.
3. **가중치 경험적**: 백테스트 전이므로 w1/w2/w3 는 직관적 값. 객관적 근거 없음.
4. **shape / stability 중복 가능성**: 시간 스케일만 다른 동일 정보일 수 있음. Phase 2 재설계 후보.
5. **Pearson 단독**: Spearman, 공적분, DTW 등은 전부 Phase 2+.
6. **생존편향 부분 제거**: 스냅샷 공시만, 완전 제거 아님.

## 참고
- [계획서 §7 MVP 공식](../plans/Sim_Money-plan.md)
- [계획서 §11 골든 회귀 테스트](../plans/Sim_Money-plan.md)
