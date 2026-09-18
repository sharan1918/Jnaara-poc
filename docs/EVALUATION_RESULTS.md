# Jnaara Belief Engine — Integration Sequence Benchmark Results

> [!IMPORTANT]
> **Methodology Clarification: Integration Sequences vs. Independent Evaluation**
>
> This document details the **5 End-to-End Integration Sequences** (138 facts across 15 enterprise entities) used to verify narrative consistency, state transition mechanics, and deterministic resolution strategy divergence.
>
> For the **formal, partition-isolated benchmark evaluation** reporting standard statistical metrics (Precision: 80.0%, Recall: 29.6%, F1: 43.2%, Specificity: 92.9%, False Positives: 2, False Negatives: 19) and failure mode diagnoses across 15 semantic categories on held-out test data, please see the primary evaluation document:
> 👉 **[docs/evaluation.md](evaluation.md)**

- **Evaluated Dataset:** `data/jnaara_memory_facts_dataset.json` (Integration Sequences 1 through 5)
- **Evaluated Strategies:** `recency` (Reliability-Weighted Recency) & `corroboration` (Independent Multi-Source Corroboration)
- **Primary / Secondary LLM Providers:** Dual orchestration with semantic inference safeguards and deterministic state control

---

## 1. Integration Sanity Scorecard Across All 5 Sequences

| Metric | Sequence 1 (Easy) | Sequence 2 (Medium) | Sequence 3 (Hard) | Sequence 4 (Hard) | Sequence 5 (Hard) | Total / Combined | Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Facts Processed** | 27 / 27 | 27 / 27 | 30 / 30 | 27 / 27 | 27 / 27 | **138 / 138 (100%)** | 🟢 0 dropped / 0 failed |
| **Extracted Claims** | 56 | 58 | 64 | 54 | 54 | **286 claims** | 🟢 High density (2.07/fact) |
| **Key Conflicts Tested** | 5 | 4 | 4 | 3 | 3 | **19 conflicts** | 🟢 Complete coverage |
| **Detection Rate** | **100% (5/5)** | **100% (4/4)** | **100% (4/4)** | **100% (3/3)** | **100% (3/3)** | **100% (19/19)** | 🟢 Flawless detection |
| **Resolution Accuracy** | **100%** | **100%** | **100%** | **100%** | **100%** | **100%** | 🟢 Ground truth aligned |
| **Rumor Suppression** | 100% | 100% | 100% | 100% | 100% | **100%** | 🟢 Unverified blogs rejected |

---

## 2. Sequence-by-Sequence Evaluation Breakdown

### Sequence 1 (Easy): Direct Contradictions & Temporal Restatements
- **Domain**: Enterprise SaaS, healthcare networks, logistics partnerships
- **Entities**: `NovaTech Inc.`, `Meridian Healthcare`, `Crestline Logistics`, `HomeMax`
- **Facts**: 27 facts (`E1` to `E27`)
- **Key Results**:
  1. *NovaTech Q4 Revenue*: Resolved preliminary `$480M` release $\rightarrow$ SEC 8-K restatement `$412M` (Accuracy: 100%).
  2. *Meridian Leadership*: Managed succession from David Park $\rightarrow$ Dr. Sarah Chen without false conflict (Accuracy: 100%).
  3. *Facility Footprint*: Reduced 142 hospitals $\rightarrow$ 134 operational facilities following rural closures (Accuracy: 100%).
  4. *Customer Progression*: Demonstrated deterministic strategy divergence on verified customer counts (`298` under recency vs `340` under corroboration).

### Sequence 2 (Medium): Cross-Source & Cross-Entity Contradictions
- **Domain**: Robotics automation, clean energy, venture holdings
- **Entities**: `Arcadia Robotics`, `Vantage Energy`, `PeakFin Capital`, `TerraMotors`, `SiemensAI`
- **Facts**: 27 facts (`M1` to `M27`)
- **Key Results**:
  1. *Customer Dependency*: Surfaced TerraMotors going-concern insolvency against Arcadia's claim of a "strong order book", leading to a `$58M` receivables write-down.
  2. *Environmental Compliance*: Replaced Vantage Energy's marketing claims with EPA Notice of Violation (4x leak rate) and `$165M` penalties/remediation.
  3. *Rumor Filtering*: Suppressed unverified blog exit rumor (`M10`) in favor of official SEC 13F filing confirming PeakFin's 8.2% stake.

### Sequence 3 (Hard): Nuanced Logical Inference Contradictions
- **Domain**: Semiconductor manufacturing, AI cloud, oncology clinical trials, biotech VC
- **Entities**: `Helios Semiconductor`, `Atlas Cloud Systems`, `Forge Therapeutics`, `Pinnacle Ventures`
- **Facts**: 30 facts (`H1` to `H30`)
- **Key Results**:
  1. *Capacity vs Inventory*: Detected logical incompatibility between Helios CEO's "capacity-constrained" claim and an 85% surge in unsold finished inventory (`$890M`).
  2. *Exclusive Supply vs Sourcing*: Caught Atlas Cloud actively qualifying alternative chip vendors and developing custom ASICs despite announcing an "exclusive" Helios partnership.
  3. *Trial Crossover Bias*: Uncovered clinical trial crossover bias in Forge's FT-400 trial, reducing claimed `34%` PFS to clean `19%` PFS.
  4. *Covert Hedging*: Flagged Pinnacle Ventures managing partner's public "zero risk" stance against SEC disclosures of a 60% downside options collar.

### Sequence 4 (Hard): FinTech & Cross-Entity Liquidity Contradictions
- **Domain**: Cross-border payments, stablecoin reserves, commercial banking, logistics settlement
- **Entities**: `AetherPay Systems`, `Valence Capital Partners`, `Solas Digital Asset Bank`, `Nordic Express Logistics`
- **Facts**: 27 facts (`F4_1` to `F4_27`)
- **Key Results**:
  1. *Reserve Duration Mismatch*: Detected contradiction between AetherPay's 100% liquid T-Bill attestation and Solas Bank's FDIC Call Report showing `62%` (`$1.12B`) locked in illiquid 5-year commercial real estate loans.
  2. *Settlement Velocity vs Injunction*: Flagged "instant settlement with zero delays" claims against Nordic Express's Delaware Chancery Court injunction revealing `$52M` in frozen funds.
  3. *Covert Credit Default Hedging*: Replaced Valence's "risk-free" guidance with disclosures of `$80M` in CDS protection purchases and a `$48M` loan impairment write-down.

### Sequence 5 (Hard): Cybersecurity Breach, Cloud SLA & Governance Contradictions
- **Domain**: Endpoint AI security, hyperscale cloud infrastructure, genomics biotech, assurance labs
- **Entities**: `CipherGuard AI`, `OmniCloud Infrastructure`, `Sentient BioTech`, `Aegis Assurance Labs`
- **Facts**: 27 facts (`F5_1` to `F5_27`)
- **Key Results**:
  1. *Breach Denial vs Forensic Proof*: Disproved CipherGuard's "zero customer compromise" statements against Sentient's 4.2TB exfiltration disclosure and Aegis Labs packet captures proving kernel driver bypass.
  2. *Uptime SLA vs Outage Penalties*: Detected contradiction between OmniCloud's 99.999% availability claim and `$28M` SLA penalty credit accruals, culminating in a restatement to `99.82%`.
  3. *Data Sovereignty vs Model Training*: Flagged FedRAMP/HIPAA in-region compliance certifications against a NeurIPS research paper revealing models were trained on 180TB of raw customer memory dumps.

---

## 3. Dual-Strategy Comparative Benchmark

| Entity & Attribute | Evaluated Claims & Evidence | `RecencyWeightedStrategy` Outcome | `CorroborationWeightedStrategy` Outcome | Strategy Agreement / Divergence Rationale |
| :--- | :--- | :---: | :---: | :--- |
| **NovaTech**<br>`enterprise customers` | **E4/E10**: `340`<br>**E12**: `200` (Blog)<br>**E26**: `298` (CEO) | **`298`** (v3, conf: 0.95)<br>*Latest CEO statement wins* | **`340`** (v2, conf: 0.98)<br>*Multi-source corroboration wins* | 🔀 **Intentional Divergence**<br>Demonstrates core strategy behavior on unconfirmed single-source updates. |
| **NovaTech**<br>`Q4 2024 revenue` | **E1**: `$480M`<br>**E7**: `$412M` (8-K) | **`$412M`** | **`$412M`** | 🤝 **Consensus Agreement**<br>Audited regulatory restatements dominate under both models. |
| **Meridian**<br>`operational hospitals` | **E5**: `142`<br>**E17**: `134` (Closures) | **`134`** | **`134`** | 🤝 **Consensus Agreement**<br>Facility footprint contractions tracked accurately. |
| **Vantage Energy**<br>`methane compliance` | **M3**: Pledges<br>**M13**: EPA violation | **`EPA Violation Notice`** | **`EPA Violation Notice`** | 🤝 **Consensus Agreement**<br>Regulatory enforcement findings supersede PR statements. |
| **Arcadia Robotics**<br>`customer relationships` | **M6**: Strong order book<br>**M12**: TerraMotors distress | **`TerraMotors Insolvent`** | **`TerraMotors Insolvent`** | 🤝 **Consensus Agreement**<br>Cross-entity partner distress correctly propagated. |
| **Forge Therapeutics**<br>`FT-400 efficacy` | **H4**: `34%` PFS<br>**H9**: Clean `19%` PFS | **`19% (Clean PFS)`** | **`19% (Clean PFS)`** | 🤝 **Consensus Agreement**<br>Scientific consensus removes clinical trial crossover bias. |
| **AetherPay Systems**<br>`reserve backing` | **F4_2**: 100% T-Bills<br>**F4_8**: 62% CRE loans | **`62% illiquid CRE loans`** | **`62% illiquid CRE loans`** | 🤝 **Consensus Agreement**<br>Regulatory call report supersedes company marketing. |
| **Valence Capital**<br>`credit facility status` | **F4_17**: Fully Performing<br>**F4_25**: Impaired ($48M) | **`Impaired ($48M)`** | **`Impaired ($48M)`** | 🤝 **Consensus Agreement**<br>SEC 10-Q impairment write-down wins over initial guidance. |
| **CipherGuard AI**<br>`CVE-2025-9981 impact` | **F5_6**: Zero compromise<br>**F5_12**: Kernel bypass | **`Kernel driver bypass`** | **`Kernel driver bypass`** | 🤝 **Consensus Agreement**<br>Independent forensic audit supersedes vendor claims. |
| **OmniCloud**<br>`availability SLA` | **F5_3**: 99.999% SLA<br>**F5_25**: 99.82% restated | **`99.82% actual`** | **`99.82% actual`** | 🤝 **Consensus Agreement**<br>SLA penalty disclosures and restatements supersede marketing. |

---

## 4. Verification Instructions

The entire 5-sequence evaluation suite can be run locally:

```bash
# Run all 49 automated unit and integration tests
uv run pytest -v

# Run the 5-sequence benchmark evaluation specifically
uv run pytest tests/test_integration.py -v
```

👉 **Complete Detailed Analysis & Deep Dives:** [docs/ACCURACY_AND_BENCHMARKS.md](ACCURACY_AND_BENCHMARKS.md)
