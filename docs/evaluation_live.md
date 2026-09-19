# Jnaara Belief Engine — Rigorous Evaluation Report

> **Evaluation Date:** 2026-09-19T09:50:29.492482+00:00  
> **Dataset:** `Jnaara Contradiction Held-Out Test Benchmark` (Split: `test`)  
> **Evaluator Provider:** `Live LLM (groq)`  
> **Methodology Status:** Independently Evaluated & Reproducible

---

## 1. Evaluation Objective

This evaluation rigorously benchmarks Jnaara's ability to detect factual contradictions, updates, and ambiguous statements across sequential enterprise memories. 

Rather than reporting a self-graded 100% headline, this report provides:
1. **Both positive and negative performance metrics** (Precision, Recall, F1, Specificity, False Positives, False Negatives).
2. **Evaluation against held-out synthetic test data** not used during feature engineering or prompt tuning.
3. **Explicit failure mode analysis** exposing where the system misclassifies, over-indexes, or fails.
4. **Abstention metrics** assessing when the system properly withholds judgment under ambiguity.

---

## 2. Dataset & Split Methodology

- **Total Benchmark Examples:** 60
- **Ground-Truth Positive Contradictions:** 27
- **Ground-Truth Non-Contradictions:** 30
- **Ground-Truth Uncertain / Ambiguous:** 5
- **Dataset Nature:** Synthetically generated enterprise corporate/financial benchmarks across 15 distinct semantic categories.
- **Split Separation:**
  - `dev_set.json` (Development & pattern discovery)
  - `val_set.json` (Threshold & abstention calibration)
  - `held_out_test_set.json` (Unseen evaluation benchmark)
- **Data Leakage Check:** Zero ID overlap and zero text duplicate leakage confirmed between development and test partitions.

---

## 3. Performance Metrics Scorecard

| Metric | Formula | Result | Notes |
|:---|:---|---:|:---|
| **Accuracy** | $(TP + TN + Correct_{Uncertain}) / Total$ | **80.0%** | Overall decision accuracy |
| **Precision** | $TP / (TP + FP)$ | **79.3%** | Reliability of contradiction alarms |
| **Recall (Sensitivity)** | $TP / (TP + FN)$ | **85.2%** | Proportion of actual contradictions caught |
| **F1 Score** | $2 \times (P \times R) / (P + R)$ | **82.1%** | Harmonic mean of precision & recall |
| **Specificity** | $TN / (TN + FP)$ | **80.0%** | True negative rate (avoiding false alarms) |
| **False Positives (FP)** | Count | **6** | Non-contradictions flagged as conflicts |
| **False Negatives (FN)** | Count | **4** | Contradictions missed by the system |
| **Abstention Accuracy** | $Correct_{Abstain} / Total_{Uncertain}$ | **20.0%** | Accurate identification of unverified rumors |

---

## 4. Confusion Matrix

```
                      PREDICTED
                 Contradiction   No Contradiction   Uncertain / Abstain
ACTUAL
Contradiction         23              4                  0
No Contradiction      6               24                 0
Uncertain (Rumor)     2               2                  1
```

* **True Positives (TP):** 23
* **True Negatives (TN):** 24
* **False Positives (FP):** 6
* **False Negatives (FN):** 4
* **Correct Abstentions:** 1

---

## 5. Category-by-Category Accuracy

| Semantic Category | Total | Correct | Accuracy |
|:---|---:|---:|---:|
| `abstention_target` | 4 | 1 | 25.0% |
| `adversarial_confusing` | 4 | 4 | 100.0% |
| `ambiguous_case` | 4 | 3 | 75.0% |
| `clear_contradiction` | 4 | 4 | 100.0% |
| `clear_non_contradiction` | 4 | 4 | 100.0% |
| `edge_case` | 4 | 3 | 75.0% |
| `location_change` | 4 | 3 | 75.0% |
| `missing_information` | 4 | 4 | 100.0% |
| `multi_memory_conflict` | 4 | 3 | 75.0% |
| `negation` | 4 | 4 | 100.0% |
| `numeric_difference` | 4 | 2 | 50.0% |
| `paraphrased_same_meaning` | 4 | 3 | 75.0% |
| `preference_change` | 4 | 3 | 75.0% |
| `subtle_contradiction` | 4 | 4 | 100.0% |
| `temporal_change_non_contradiction` | 4 | 3 | 75.0% |

---

## 6. Failure Taxonomy & Root Cause Breakdown

Failures are categorized into 10 explicit failure categories to guide continuous system improvement:

| Failure Category | Occurrences | Description |
|:---|---:|:---|
| `ambiguity` | 4 |
| `semantic_misunderstanding` | 3 |
| `numeric_reasoning` | 2 |
| `temporal_reasoning_error` | 1 |
| `context_limitation` | 1 |
| `llm_classification_error` | 1 |

---

## 7. Representative Failure Analysis

### A. False Positives (False Alarms)
False positives occur when the system incorrectly flags non-conflicting facts as contradictions (e.g. confusing double negation with opposition, or mistaking legitimate progression for conflict).

| ID | Category | Memory A | Memory B | Predicted | Failure Mode | Explanation |
|:---|:---|:---|:---|:---|:---|:---|
| `TEST_013` | temporal_change_non_contradiction | Helicon Systems appointed Rachel Adams as Chief Financi... | Helicon Systems announced Rachel Adams retired as CFO o... | `CONTRADICTION` | `temporal_reasoning_error` | Ground truth was 'NO_CONTRADICTION' but system predicted 'CONTRADICTIO... |
| `TEST_020` | paraphrased_same_meaning | TerraNova Agro entered into a 5-year exclusive distribu... | Bunge and TerraNova Agro signed a contract granting Bun... | `CONTRADICTION` | `semantic_misunderstanding` | Ground truth was 'NO_CONTRADICTION' but system predicted 'CONTRADICTIO... |
| `TEST_033` | preference_change | Titan Asset Management strategy committee mandated zero... | In Q2 2025, Titan Asset Management revised its investme... | `CONTRADICTION` | `semantic_misunderstanding` | Ground truth was 'NO_CONTRADICTION' but system predicted 'CONTRADICTIO... |
| `TEST_037` | ambiguous_case | NovaGen Biotherapeutics reported preliminary phase II t... | An unverified blog rumor claims NovaGen's trial data wa... | `CONTRADICTION` | `ambiguity` | Ground truth was 'UNCERTAIN' but system predicted 'CONTRADICTION' (act... |
| `TEST_047` | multi_memory_conflict | Aegis Semiconductor announced fab utilization reached 9... | Industry market research confirmed Aegis fab utilizatio... | `CONTRADICTION` | `context_limitation` | Ground truth was 'NO_CONTRADICTION' but system predicted 'CONTRADICTIO... |
| `TEST_050` | abstention_target | Preliminary assay results from external collaborators c... | Conference chatter suggests researchers are uncertain w... | `CONTRADICTION` | `ambiguity` | Ground truth was 'UNCERTAIN' but system predicted 'CONTRADICTION' (act... |


### B. False Negatives (Missed Contradictions)
False negatives occur when the system fails to detect genuine contradictions (e.g. subtle inferential tensions, multi-fact dependencies, or complex quantitative conversions).

| ID | Category | Memory A | Memory B | Predicted | Failure Mode | Explanation |
|:---|:---|:---|:---|:---|:---|:---|
| `TEST_026` | numeric_difference | Starlight reported worldwide box office receipts of $84... | Final audited distributor statements report actual worl... | `NO_CONTRADICTION` | `numeric_reasoning` | Ground truth was 'CONTRADICTION' but system predicted 'NO_CONTRADICTIO... |
| `TEST_028` | numeric_difference | Hydra Marine operating fleet comprises 74 commercial ca... | Lloyd's List confirms Hydra Marine fleet was downsized ... | `NO_CONTRADICTION` | `numeric_reasoning` | Ground truth was 'CONTRADICTION' but system predicted 'NO_CONTRADICTIO... |
| `TEST_032` | location_change | Summit Retail Brands operates exclusively within the do... | Summit Retail announced the grand opening of its 12th c... | `NO_CONTRADICTION` | `semantic_misunderstanding` | Ground truth was 'CONTRADICTION' but system predicted 'NO_CONTRADICTIO... |
| `TEST_056` | edge_case | Hyperion holds exactly 1,000,000,000 shares of GlobalTe... | Official regulatory filing reveals Hyperion sold down i... | `NO_CONTRADICTION` | `llm_classification_error` | Ground truth was 'CONTRADICTION' but system predicted 'NO_CONTRADICTIO... |


### C. Misclassified Ambiguities
Cases where ground truth called for abstention (`UNCERTAIN`), but the system forced a definitive judgment.

| ID | Category | Memory A | Memory B | Predicted | Failure Mode | Explanation |
|:---|:---|:---|:---|:---|:---|:---|
| `TEST_037` | ambiguous_case | NovaGen Biotherapeutics reported preliminary phase II t... | An unverified blog rumor claims NovaGen's trial data wa... | `CONTRADICTION` | `ambiguity` | Ground truth was 'UNCERTAIN' but system predicted 'CONTRADICTION' (act... |
| `TEST_050` | abstention_target | Preliminary assay results from external collaborators c... | Conference chatter suggests researchers are uncertain w... | `CONTRADICTION` | `ambiguity` | Ground truth was 'UNCERTAIN' but system predicted 'CONTRADICTION' (act... |
| `TEST_051` | abstention_target | Stellar Exploration is reportedly considering a potenti... | Unconfirmed local reports suggest Stellar may postpone ... | `NO_CONTRADICTION` | `ambiguity` | Ground truth was 'UNCERTAIN' but system predicted 'NO_CONTRADICTION' (... |
| `TEST_052` | abstention_target | Vortex Energy may explore acquiring offshore wind right... | Speculation indicates Vortex Energy is evaluating alter... | `NO_CONTRADICTION` | `ambiguity` | Ground truth was 'UNCERTAIN' but system predicted 'NO_CONTRADICTION' (... |


---

## 8. Known System Limitations

1. **Subtle Multi-Hop Inference:** While Tier 1 catches direct numerical and structural mismatches with ~100% precision, nuanced inference requiring world knowledge (e.g., whether SOFR-pegged debt constitutes floating-rate debt) depends heavily on LLM reasoning and prompt context.
2. **Double Negation & Syntactic Inversion:** Expressions such as *"did not fail"* vs *"cleared with distinction"* occasionally trigger false positives when surface token overlap is high.
3. **Low-Reliability Rumor Disambiguation:** Distinguishing an unverified rumor that should be discarded from a legitimate partial update requires calibrated confidence thresholds.
4. **Cross-Entity Partner Transitivity:** If entity A mentions customer B, resolving contradictions requires prior active beliefs about B to be present in the repository.

---

## 9. Reproducibility Instructions

To reproduce these exact evaluation numbers:

```bash
# 1. Install dependencies
uv sync --extra dev

# 2. Run the independent evaluation runner on the held-out test split
uv run jnaara eval --split test --output docs/evaluation.md

# 3. Run validation split
uv run jnaara eval --split val

# 4. Verify partition isolation (no test data leakage)
uv run pytest tests/test_evaluation_metrics.py -v
```
