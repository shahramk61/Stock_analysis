# Quantitative Analyst - TradingAgents Integration Design

**Status**: Phase 1 - Design  
**Date**: 2026-05-16  
**Goal**: Define how to integrate the Quantitative Analyst into TradingAgents cleanly and effectively.

---

## 1. Recommended Integration Approach

**Primary Recommendation**: Add the Quantitative Analyst as a **new selectable analyst type** inside TradingAgents (similar to `market_analyst`, `fundamentals_analyst`, etc.).

### Why this approach?
- Follows the existing architecture and patterns in TradingAgents.
- Easy to enable/disable via the `selected_analysts` parameter.
- Allows it to participate naturally in the analyst → researcher debate flow.
- Keeps the system modular and consistent.

---

## 2. Agent Role & Responsibilities

| Aspect                    | Recommendation |
|---------------------------|----------------|
| **Primary Role**          | Quantitative Specialist / Data Provider |
| **v1 Role**               | Data Provider only (recommended) |
| **v2+ Potential**         | Light debate participation (optional) |
| **Main Strength**         | Delivers model-driven forecasts + risk + technical/quant signals |
| **Interaction Style**     | Provides rich structured + interpreted data for Researchers and Trader to use |

**Key Principle (v1)**:  
The Quantitative Analyst acts as a **Data Provider**. It supplies high-quality quantitative reports rather than actively debating. Debate participation is deferred to v2+ if needed.

---

## 3. Inputs & Outputs

### Inputs (from state)
- `ticker` / `company_of_interest`
- Analysis date (if available)
- Shared conversation state

### Outputs
- `quantitative_report` (main deliverable)
- Updated messages in the shared state

**Report Style**: Hybrid (Natural language + structured tables + short interpretations + Key Takeaways)

---

## 4. Proposed Flow Integration

```
Analyst Team (parallel)
├── Fundamentals Analyst
├── Sentiment Analyst
├── News Analyst
├── Market Analyst (Technical)
└── Quantitative Analyst   ← New
        │
        ▼
Researcher Team (Bull vs Bear debate)
        │
        ▼
Trader
        │
        ▼
Risk Management
```

The Quantitative Analyst runs in parallel with other analysts and feeds its report into the Researcher debate.

---

## 5. Key Design Decisions

| Decision                        | Recommended Option          | Rationale |
|---------------------------------|-----------------------------|---------|
| Run by default?                 | Optional (`selected_analysts`) | Gives users control |
| Use LLM heavily?                | Light use only              | Rely mostly on our signals package |
| Participate in debate?          | Limited / Data provider     | Avoid role overlap with Researchers |
| Output format                   | Hybrid + Key Takeaways      | Most useful for downstream agents |
| Conviction included?            | Yes                         | Helps Researchers weigh the data |

---

## 6. Open Questions

- Should the Quantitative Analyst also be allowed to speak during the Researcher debate, or only provide its report?
- Do we want a dedicated tool node for it (like other analysts have), or keep it simple?
- How should we handle the `llm` parameter (since our agent is mostly signals-driven)?
- Should we eventually contribute this agent back to the main TradingAgents repo?

---

## 7. Next Steps (After Design)

1. Finalize this design document.
2. Create integration instructions / code skeleton.
3. Test the agent inside a minimal TradingAgents-style workflow.
4. Decide on long-term contribution strategy.

---

**Status**: Design document created. Ready for review and discussion.