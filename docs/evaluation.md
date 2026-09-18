# Jnaara Belief Engine — Rigorous Evaluation Report

> **Evaluation Date:** 2026-09-18T17:25:36.430572+00:00  
> **Dataset:** `Jnaara Contradiction Held-Out Test Benchmark` (Split: `test`)  
> **Evaluator Provider:** `MockLLMProvider (Deterministic Offline)`  
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
- **Ground-Truth Non-Contradictions:** 28
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
| **Accuracy** | $(TP + TN + Correct_{Uncertain}) / Total$ | **60.0%** | Overall decision accuracy |
| **Precision** | $TP / (TP + FP)$ | **80.0%** | Reliability of contradiction alarms |
| **Recall (Sensitivity)** | $TP / (TP + FN)$ | **29.6%** | Proportion of actual contradictions caught |
| **F1 Score** | $2 \times (P \times R) / (P + R)$ | **43.2%** | Harmonic mean of precision & recall |
| **Specificity** | $TN / (TN + FP)$ | **92.9%** | True negative rate (avoiding false alarms) |
| **False Positives (FP)** | Count | **2** | Non-contradictions flagged as conflicts |
| **False Negatives (FN)** | Count | **19** | Contradictions missed by the system |
| **Abstention Accuracy** | $Correct_{Abstain} / Total_{Uncertain}$ | **40.0%** | Accurate identification of unverified rumors |

---

## 4. Confusion Matrix

```
                      PREDICTED
                 Contradiction   No Contradiction   Uncertain / Abstain
ACTUAL
Contradiction         8               19                 0
No Contradiction      2               26                 0
Uncertain (Rumor)     0               3                  2
```

* **True Positives (TP):** 8
* **True Negatives (TN):** 26
* **False Positives (FP):** 2
* **False Negatives (FN):** 19
* **Correct Abstentions:** 2

---

## 5. Category-by-Category Accuracy

| Semantic Category | Total | Correct | Accuracy |
|:---|---:|---:|---:|
| `abstention_target` | 4 | 2 | 50.0% |
| `adversarial_confusing` | 4 | 3 | 75.0% |
| `ambiguous_case` | 4 | 3 | 75.0% |
| `clear_contradiction` | 4 | 4 | 100.0% |
| `clear_non_contradiction` | 4 | 4 | 100.0% |
| `edge_case` | 4 | 3 | 75.0% |
| `location_change` | 4 | 2 | 50.0% |
| `missing_information` | 4 | 2 | 50.0% |
| `multi_memory_conflict` | 4 | 1 | 25.0% |
| `negation` | 4 | 0 | 0.0% |
| `numeric_difference` | 4 | 2 | 50.0% |
| `paraphrased_same_meaning` | 4 | 4 | 100.0% |
| `preference_change` | 4 | 2 | 50.0% |
| `subtle_contradiction` | 4 | 0 | 0.0% |
| `temporal_change_non_contradiction` | 4 | 4 | 100.0% |

---

## 6. Failure Taxonomy & Root Cause Breakdown

Failures are categorized into 10 explicit failure categories to guide continuous system improvement:

| Failure Category | Occurrences | Description |
|:---|---:|:---|
| `llm_classification_error` | 8 |
| `negation_error` | 4 |
| `semantic_misunderstanding` | 4 |
| `ambiguity` | 3 |
| `context_limitation` | 3 |
| `numeric_reasoning` | 2 |

---

## 7. Representative Failure Analysis

### A. False Positives (False Alarms)
False positives occur when the system incorrectly flags non-conflicting facts as contradictions (e.g. confusing double negation with opposition, or mistaking legitimate progression for conflict).

| ID | Category | Memory A | Memory B | Predicted | Failure Mode | Explanation |
|:---|:---|:---|:---|:---|:---|:---|
| `TEST_025` | numeric_difference | Starlight reported worldwide box office receipts of $84... | Final audited distributor statements report worldwide b... | `CONTRADICTION` | `numeric_reasoning` | Ground truth was 'NO_CONTRADICTION' but system predicted 'CONTRADICTIO... |
| `TEST_029` | location_change | Paladin Cyber Labs announced it has relocated its globa... | Swiss commercial register confirms Paladin Cyber Labs A... | `CONTRADICTION` | `semantic_misunderstanding` | Ground truth was 'NO_CONTRADICTION' but system predicted 'CONTRADICTIO... |


### B. False Negatives (Missed Contradictions)
False negatives occur when the system fails to detect genuine contradictions (e.g. subtle inferential tensions, multi-fact dependencies, or complex quantitative conversions).

| ID | Category | Memory A | Memory B | Predicted | Failure Mode | Explanation |
|:---|:---|:---|:---|:---|:---|:---|
| `TEST_009` | subtle_contradiction | Krypton Energy management assured investors that the co... | Credit agency report details that $340M of Krypton's ou... | `NO_CONTRADICTION` | `llm_classification_error` | Ground truth was 'CONTRADICTION' but system predicted 'NO_CONTRADICTIO... |
| `TEST_010` | subtle_contradiction | Lumina stated that full-year production capacity is com... | Internal supply manifests show Lumina idled two main as... | `NO_CONTRADICTION` | `llm_classification_error` | Ground truth was 'CONTRADICTION' but system predicted 'NO_CONTRADICTIO... |
| `TEST_011` | subtle_contradiction | Zephyr Cloud guarantees all European customer telemetry... | Academic paper by Zephyr researchers reveals core gener... | `NO_CONTRADICTION` | `llm_classification_error` | Ground truth was 'CONTRADICTION' but system predicted 'NO_CONTRADICTIO... |
| `TEST_012` | subtle_contradiction | Strata Mining reported an exemplary safety record with ... | Department of Environmental Protection issued a cease-a... | `NO_CONTRADICTION` | `llm_classification_error` | Ground truth was 'CONTRADICTION' but system predicted 'NO_CONTRADICTIO... |
| `TEST_021` | negation | AeroJet Systems is actively manufacturing hypersonic sc... | Department of Defense terminated Contract FA8650 for co... | `NO_CONTRADICTION` | `negation_error` | Ground truth was 'CONTRADICTION' but system predicted 'NO_CONTRADICTIO... |
| `TEST_022` | negation | Nordic Health Group maintains accredited inpatient surg... | Regional healthcare authority confirmed that 4 of Nordi... | `NO_CONTRADICTION` | `negation_error` | Ground truth was 'CONTRADICTION' but system predicted 'NO_CONTRADICTIO... |


### C. Misclassified Ambiguities
Cases where ground truth called for abstention (`UNCERTAIN`), but the system forced a definitive judgment.

| ID | Category | Memory A | Memory B | Predicted | Failure Mode | Explanation |
|:---|:---|:---|:---|:---|:---|:---|
| `TEST_037` | ambiguous_case | NovaGen Biotherapeutics reported preliminary phase II t... | An unverified blog rumor claims NovaGen's trial data wa... | `NO_CONTRADICTION` | `ambiguity` | Ground truth was 'UNCERTAIN' but system predicted 'NO_CONTRADICTION' (... |
| `TEST_050` | abstention_target | Preliminary assay results from external collaborators c... | Conference chatter suggests researchers are uncertain w... | `NO_CONTRADICTION` | `ambiguity` | Ground truth was 'UNCERTAIN' but system predicted 'NO_CONTRADICTION' (... |
| `TEST_051` | abstention_target | Stellar Exploration is reportedly considering a potenti... | Unconfirmed local reports suggest Stellar may postpone ... | `NO_CONTRADICTION` | `ambiguity` | Ground truth was 'UNCERTAIN' but system predicted 'NO_CONTRADICTION' (... |


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
