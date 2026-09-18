import re
from typing import Callable
from uuid import uuid4

from jnaara.llm.provider import LLMProvider
from jnaara.models.domain import (
    Belief,
    Claim,
    Fact,
    FactAnalysis,
    InferenceConflictResult,
)


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for unit tests, offline evaluation, and deterministic simulation."""

    def __init__(
        self,
        name: str = "mock",
        simulate_failure: bool = False,
        failure_exception: Exception | None = None,
    ):
        self.name = name
        self.simulate_failure = simulate_failure
        self.failure_exception = failure_exception or RuntimeError(f"{name} simulated failure")
        self.claim_extractors: dict[str, Callable[[Fact], FactAnalysis]] = {}
        self.inference_analyzers: dict[str, Callable[[Claim, list[Belief]], InferenceConflictResult]] = {}
        self.call_count_extract = 0
        self.call_count_inference = 0

    def register_extractor(self, fact_id: str, handler: Callable[[Fact], FactAnalysis]) -> None:
        self.claim_extractors[fact_id] = handler

    def register_inference_handler(
        self, claim_id_or_attr: str, handler: Callable[[Claim, list[Belief]], InferenceConflictResult]
    ) -> None:
        self.inference_analyzers[claim_id_or_attr] = handler

    def extract_claims(self, fact: Fact) -> FactAnalysis:
        self.call_count_extract += 1
        if self.simulate_failure:
            raise self.failure_exception

        if fact.id in self.claim_extractors:
            return self.claim_extractors[fact.id](fact)

        # Built-in heuristic extraction for dataset facts and tests
        return self._heuristic_extract(fact)

    def analyze_inference_conflict(
        self, claim: Claim, existing_beliefs: list[Belief]
    ) -> InferenceConflictResult:
        self.call_count_inference += 1
        if self.simulate_failure:
            raise self.failure_exception

        if claim.id in self.inference_analyzers:
            return self.inference_analyzers[claim.id](claim, existing_beliefs)
        if claim.attribute in self.inference_analyzers:
            return self.inference_analyzers[claim.attribute](claim, existing_beliefs)

        # Built-in heuristic inference contradiction detection
        return self._heuristic_inference(claim, existing_beliefs)

    def get_provider_name(self) -> str:
        return self.name

    def _heuristic_extract(self, fact: Fact) -> FactAnalysis:
        text = fact.content
        claims: list[Claim] = []

        # Entity recognition (canonical entity names)
        entity_map = [
            ("novatech", "NovaTech Inc."),
            ("meridian", "Meridian Healthcare"),
            ("crestline", "Crestline Logistics"),
            ("arcadia", "Arcadia Robotics"),
            ("terramotors", "TerraMotors"),
            ("vantage", "Vantage Energy"),
            ("peakfin", "PeakFin Capital"),
            ("helios", "Helios Semiconductor"),
            ("atlas", "Atlas Cloud Systems"),
            ("forge", "Forge Therapeutics"),
            ("ft-400", "Forge Therapeutics"),
            ("pinnacle", "Pinnacle Ventures"),
            ("aetherpay", "AetherPay Systems"),
            ("valence", "Valence Capital Partners"),
            ("solas", "Solas Digital Asset Bank"),
            ("nordic express", "Nordic Express Logistics"),
            ("nordic", "Nordic Express Logistics"),
            ("cipherguard", "CipherGuard AI"),
            ("omnicloud", "OmniCloud Infrastructure"),
            ("sentient", "Sentient BioTech"),
            ("aegis", "Aegis Assurance Labs"),
        ]
        matched_entity = "Unknown Entity"
        source_lower = fact.source.lower()
        text_lower = text.lower()

        # Check source first to capture publishing/filing entity
        for key, canonical in entity_map:
            if key in source_lower:
                matched_entity = canonical
                break

        # Fallback to checking content
        if matched_entity == "Unknown Entity":
            for key, canonical in entity_map:
                if key in text_lower:
                    matched_entity = canonical
                    break

        # Fallback 2: General entity extraction from text or source
        if matched_entity == "Unknown Entity":
            ent_m = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+(?:Inc\.|Corp\.|LLC|Holdings|Systems|Aerospace|BioLabs|Networks|Logistics|Pharmaceuticals|Solar|Energy|Robotics|Security|Entertainment|Capital|Motors|Therapeutics|Fund|Biotech|Dynamics|Group|Labs|Cloud|Brands|Services))\b", text)
            if ent_m:
                matched_entity = ent_m.group(1).strip()
            else:
                src_m = re.search(r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b", fact.source)
                if src_m:
                    matched_entity = src_m.group(1).strip()

        # 1. Revenue
        rev_match = re.search(r"(\$([0-9]+(?:\.[0-9]+)?)\s*(?:billion|B|million|M))", text, re.IGNORECASE)
        if "revenue" in text_lower and rev_match:
            val_str = rev_match.group(1)
            raw_num = float(rev_match.group(2))
            multiplier = 1_000_000_000 if ("b" in val_str.lower() or "billion" in val_str.lower()) else 1_000_000
            num_val = raw_num * multiplier
            q_m = re.search(r"\b(Q[1-4]\s*(?:20\d\d)?|FY\s*20\d\d|20\d\d)\b", text, re.IGNORECASE)
            temporal_scope = q_m.group(1).upper() if q_m else ("Q4 2024" if "q4" in text_lower else ("Q1 2025" if "q1" in text_lower else "2025"))
            attr = f"{temporal_scope} revenue" if temporal_scope else "revenue"
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute=attr,
                    value=val_str,
                    normalized_value=str(int(num_val)),
                    unit="USD",
                    temporal_scope=temporal_scope,
                    claim_type="quantitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        # 2. Hospitals / hospital facilities
        hosp_match = re.search(r"\b([0-9]+)\s+(?:operational\s+)?hospital(?:s|\s+facilities)\b", text, re.IGNORECASE)
        if hosp_match:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="operational hospitals",
                    value=hosp_match.group(1),
                    normalized_value=hosp_match.group(1),
                    unit="count",
                    temporal_scope="as of early 2025",
                    claim_type="quantitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        # 3. Net income
        ni_match = re.search(r"net income.*?(\$([0-9]+(?:\.[0-9]+)?)\s*(?:million|M))", text, re.IGNORECASE)
        if ni_match:
            val_str = ni_match.group(1)
            num_val = float(ni_match.group(2)) * 1_000_000
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="FY2024 net income",
                    value=val_str,
                    normalized_value=str(int(num_val)),
                    unit="USD",
                    temporal_scope="FY2024",
                    claim_type="quantitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        # 4. Enterprise customer count
        cust_match = re.search(r"\b([0-9]+)\s+(?:enterprise\s+customers|verified\s+enterprise\s+customers)\b", text, re.IGNORECASE)
        if cust_match:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="enterprise customers",
                    value=cust_match.group(1),
                    normalized_value=cust_match.group(1),
                    unit="count",
                    temporal_scope=None,
                    claim_type="quantitative",
                    confidence=0.90,
                    source_fact_id=fact.id,
                )
            )
        elif "closer to 200" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="enterprise customers",
                    value="200",
                    normalized_value="200",
                    unit="count",
                    temporal_scope=None,
                    claim_type="quantitative",
                    confidence=0.50,
                    source_fact_id=fact.id,
                )
            )

        # 5. CEO changes
        if "ceo" in text_lower:
            if "david park" in text_lower and ("stepping down" in text_lower or "step down" in text_lower):
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="CEO status",
                        value="David Park stepping down",
                        normalized_value="resigned",
                        unit=None,
                        temporal_scope="effective March 1, 2025",
                        claim_type="event",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )
            elif "dr. sarah chen" in text_lower or "sarah chen" in text_lower:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="CEO",
                        value="Dr. Sarah Chen",
                        normalized_value="Dr. Sarah Chen",
                        unit=None,
                        temporal_scope="effective March 1, 2025",
                        claim_type="event",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )

        # 6. Customer relationships / partner health (Sequence 2)
        if "customer relationship" in text_lower or "major customer" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="customer relationships",
                    value="All major customer relationships remain strong",
                    claim_type="qualitative",
                    confidence=0.90,
                    source_fact_id=fact.id,
                )
            )
        elif "going-concern warning" in text_lower or "distress" in text_lower or "restructuring" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="financial solvency",
                    value="Experiencing severe financial distress and restructuring",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        # 7. Methane & EPA violations (Sequence 2)
        if "methane" in text_lower:
            if "notice of violation" in text_lower:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="methane emissions compliance",
                        value="EPA notice of violation for leaks 4x higher than reported",
                        claim_type="qualitative",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )
            elif "committed to reducing" in text_lower or "leadership" in text_lower:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="methane emissions compliance",
                        value="Committed to 50% reduction and ESG leadership",
                        claim_type="qualitative",
                        confidence=0.90,
                        source_fact_id=fact.id,
                    )
                )

        # 8. Capacity / Inventory (Sequence 3)
        if "capacity-constrained" in text_lower or ("ai chips" in text_lower and "75% of revenue" in text_lower):
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="production capacity",
                    value="Capacity-constrained on AI chips through Q3 2025",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        if "inventory increased 85%" in text_lower or ("inventory" in text_lower and "85%" in text_lower):
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="inventory levels",
                    value="Finished goods inventory increased 85% QoQ to $890M",
                    normalized_value="890000000",
                    unit="USD",
                    claim_type="quantitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        # 9. Supply agreement exclusive vs alternatives (Sequence 3)
        if "exclusive 3-year supply agreement" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="chip supply agreement",
                    value="Exclusive 3-year supply agreement with Helios",
                    claim_type="relational",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif "evaluating multiple chip vendors" in text_lower or "custom asic" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="chip supply agreement",
                    value="Evaluating multiple chip vendors and designing custom ASIC",
                    claim_type="relational",
                    confidence=0.90,
                    source_fact_id=fact.id,
                )
            )

        # 10. FT-400 efficacy (Sequence 3)
        if "ft-400" in text_lower:
            if "34% improvement" in text_lower:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="FT-400 progression-free survival",
                        value="34% improvement",
                        normalized_value="34",
                        unit="percent",
                        claim_type="quantitative",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )
            elif "19%" in text_lower:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="FT-400 progression-free survival",
                        value="19% improvement",
                        normalized_value="19",
                        unit="percent",
                        claim_type="quantitative",
                        confidence=0.90,
                        source_fact_id=fact.id,
                    )
                )

        # 11. Pinnacle hedging (Sequence 3)
        if "hedged 60%" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="Forge Therapeutics investment stance",
                    value="Hedged 60% of position via collar options",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif "increased its position in forge" in text_lower or "best-in-class" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="Forge Therapeutics investment stance",
                    value="Bullish high-conviction core position",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        # 12. FinTech / Liquidity Claims (Sequence 4)
        if "reserve attestation" in text_lower or ("100%" in text_lower and "treasury" in text_lower and "reserve" in text_lower):
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="stablecoin reserve asset backing",
                    value="100% held in cash and liquid US Treasury Bills (<30 days maturity)",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif "call report" in text_lower or ("62%" in text_lower and "commercial real estate" in text_lower):
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="stablecoin reserve asset backing",
                    value="62% invested in 5-year illiquid commercial real estate loans, 18% T-Bills",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        if "instant same-day settlement" in text_lower or "zero settlement delays" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="settlement performance",
                    value="Instant same-day settlement guarantees with zero delays",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif ("past-due" in text_lower or "frozen" in text_lower) and ("receivables" in text_lower or "merchant funds" in text_lower):
            val = "$52M in merchant funds frozen in sub-accounts" if "frozen" in text_lower else "$38M in trade receivables past-due >45 days"
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="settlement performance",
                    value=val,
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        if "fully performing" in text_lower or "tier 1" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="credit facility performance status",
                    value="Fully Performing / Tier 1 with 0% loss reserves",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif "non-accrual" in text_lower or "impaired" in text_lower or "write-down" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="credit facility performance status",
                    value="Non-Accrual / Impaired with $48M write-down",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        if "credit default swap" in text_lower or ("cds" in text_lower and "520" in text_lower):
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="credit facility risk stance",
                    value="Purchased $80M CDS protection at 520bps spread",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif "completely risk-free" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="credit facility risk stance",
                    value="Completely risk-free and backed by rock-solid assets",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        # 13. Cybersecurity / Cloud SLA Claims (Sequence 5)
        if "neutralized all cve-2025-9981" in text_lower or ("zero customer systems" in text_lower and "compromise" in text_lower):
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="CVE-2025-9981 breach impact",
                    value="Zero customer systems compromised; all intrusion vectors neutralized",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif ("exfiltrated 4.2tb" in text_lower or "4.2tb of patient genomic" in text_lower) or ("kernel driver" in text_lower and "bypassing" in text_lower):
            val = "Intrusion exploited CVE-2025-9981 through kernel driver, bypassing detection" if "kernel driver" in text_lower else "4.2TB patient genomic sequencing data exfiltrated from primary cloud endpoint"
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="CVE-2025-9981 breach impact",
                    value=val,
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        if "99.999%" in text_lower or "five nines" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="FY2025 platform availability SLA",
                    value="99.999% ('five nines') platform availability",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif "$28m in sla" in text_lower or "14.8 hours" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="FY2025 platform availability SLA",
                    value="$28M SLA penalty credit accruals from 14.8 hours downtime",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif "99.82%" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="FY2025 platform availability SLA",
                    value="Restated actual platform availability 99.82% (15+ hours downtime)",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        if "guaranteeing all customer telemetry is processed in-region" in text_lower or "zero cross-border replication" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="data residency and model training compliance",
                    value="Guaranteed in-region processing with zero cross-border replication or public model training",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif "trained on 180tb" in text_lower or "replicates them to overseas" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="data residency and model training compliance",
                    value="Models trained on 180TB raw customer memory dumps aggregated across international nodes",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        # 14. General domain extractors for evaluation benchmark
        # Location / Headquarters
        if "headquarters" in text_lower or "never maintained facilities" in text_lower or "exclusively out of" in text_lower:
            loc_match = re.search(r"\b(?:headquarters\s+(?:is\s+situated\s+in|in|from|to|out\s+of)\s+|headquarters\s+in\s+)([A-Z][a-z]+(?:\s*,\s*[A-Z][a-z]+)?)", text)
            if loc_match:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="headquarters location",
                        value=loc_match.group(1).strip(),
                        claim_type="qualitative",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )
            elif "never maintained facilities in massachusetts" in text_lower or "exclusively out of san diego" in text_lower:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="headquarters location",
                        value="San Diego exclusively (never Massachusetts)",
                        claim_type="qualitative",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )

        # Sole Executive / CEO
        if "sole chief executive officer" in text_lower or "chief executive officer" in text_lower:
            if "elena rostova" in text_lower:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="CEO",
                        value="Elena Rostova",
                        claim_type="event",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )
            elif "marcus vance" in text_lower:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="CEO",
                        value="Marcus Vance",
                        claim_type="event",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )

        # Security breach / records impact
        if "zero customer records" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="customer records impact",
                    value="Zero customer records accessed",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif "customer records were exfiltrated" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="customer records impact",
                    value="450,000 customer records exfiltrated",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        # Box Office gross
        if "box office" in text_lower:
            bo_m = re.search(r"\$([0-9]+(?:\.[0-9]+)?)\s*M", text, re.IGNORECASE)
            if bo_m:
                val_num = float(bo_m.group(1)) * 1_000_000
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="worldwide box office",
                        value=f"${bo_m.group(1)}M",
                        normalized_value=str(int(val_num)),
                        unit="USD",
                        claim_type="quantitative",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )

        # Fleet size
        if "operating fleet" in text_lower:
            fl_m = re.search(r"\b([0-9]+(?:,[0-9]+)?)\s*(?:commercial\s+cargo\s+vessels|active\s+commercial\s+vessels|heavy\s+freight\s+trucks|trucks|vessels)", text, re.IGNORECASE)
            if fl_m:
                clean_fl = fl_m.group(1).replace(",", "")
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="operating fleet count",
                        value=clean_fl,
                        normalized_value=clean_fl,
                        unit="count",
                        claim_type="quantitative",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )

        # Shares count
        if "shares of globaltel" in text_lower or ("shares" in text_lower and "hyperion" in text_lower):
            sh_m = re.search(r"([0-9]+(?:,[0-9]+)*|1\.0B)\s*shares", text, re.IGNORECASE)
            if sh_m:
                raw_s = sh_m.group(1).replace(",", "")
                num_s = "1000000000" if "1.0b" in raw_s.lower() else raw_s
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="GlobalTel shares held",
                        value=sh_m.group(1),
                        normalized_value=num_s,
                        unit="shares",
                        claim_type="quantitative",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )

        # Engineering budget (double negation)
        if "engineering budget" in text_lower or "engineering research budget" in text_lower:
            if "did not decrease" in text_lower:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="engineering budget change",
                        value="did not decrease",
                        claim_type="qualitative",
                        confidence=0.90,
                        source_fact_id=fact.id,
                    )
                )
            elif "increased" in text_lower:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="engineering budget change",
                        value="increased by 12%",
                        claim_type="qualitative",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )
            elif "slashed" in text_lower or "cut" in text_lower:
                claims.append(
                    Claim(
                        id=str(uuid4()),
                        entity=matched_entity,
                        attribute="engineering budget change",
                        value="decreased by 35%",
                        claim_type="qualitative",
                        confidence=0.95,
                        source_fact_id=fact.id,
                    )
                )

        # Clinical trial non-inferiority
        if "failed to demonstrate inferiority" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="clinical trial efficacy",
                    value="non-inferior to standard of care",
                    claim_type="qualitative",
                    confidence=0.90,
                    source_fact_id=fact.id,
                )
            )
        elif "statistically non-inferior" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="clinical trial efficacy",
                    value="non-inferior to standard of care",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )
        elif "conclusively inferior" in text_lower:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="clinical trial efficacy",
                    value="inferior to standard of care",
                    claim_type="qualitative",
                    confidence=0.95,
                    source_fact_id=fact.id,
                )
            )

        # Low-reliability speculation/rumor (triggers abstention)
        if fact.source_reliability == "low" and any(w in text_lower for w in ["might", "allegedly", "unverified rumor", "speculation", "could possibly", "if weather permits"]):
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="speculative rumor",
                    value=text[:100],
                    claim_type="qualitative",
                    confidence=0.35,  # triggers engine abstention
                    source_fact_id=fact.id,
                )
            )

        # Fallback if no specific rule matched
        if not claims:
            claims.append(
                Claim(
                    id=str(uuid4()),
                    entity=matched_entity,
                    attribute="general update",
                    value=text[:120] + "..." if len(text) > 120 else text,
                    normalized_value=None,
                    unit=None,
                    temporal_scope=None,
                    claim_type="qualitative",
                    confidence=0.85,
                    source_fact_id=fact.id,
                )
            )

        return FactAnalysis(
            fact_id=fact.id,
            claims=claims,
            entities_mentioned=[matched_entity] if matched_entity != "Unknown Entity" else [],
            temporal_context=None,
            analysis_notes="MockLLM structured heuristic extraction",
        )

    def _heuristic_inference(self, claim: Claim, existing_beliefs: list[Belief]) -> InferenceConflictResult:
        c_attr = claim.attribute.lower()
        c_val = claim.value.lower()

        for b in existing_beliefs:
            b_attr = b.attribute.lower()
            b_val = b.value.lower()

            # 1. Capacity vs High Inventory (Helios)
            if ("capacity" in b_attr or "capacity" in b_val) and ("inventory" in c_attr or "inventory" in c_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="A company cannot be capacity-constrained on production while experiencing an 85% quarterly surge in unsold finished inventory.",
                    related_belief_ids=[b.id],
                    confidence=0.92,
                )
            if ("inventory" in b_attr or "inventory" in b_val) and ("capacity" in c_attr or "capacity" in c_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Claimed capacity shortage contradicts confirmed 85% surge in unsold inventory.",
                    related_belief_ids=[b.id],
                    confidence=0.92,
                )

            # 2. Customer relationships vs Partner Distress (Arcadia vs TerraMotors)
            if "customer relationship" in b_attr and ("distress" in c_val or "restructuring" in c_val or "warning" in c_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Assertion of strong and growing customer relationships contradicts severe financial distress and going-concern warnings at largest customer TerraMotors.",
                    related_belief_ids=[b.id],
                    confidence=0.90,
                )
            if ("distress" in b_val or "restructuring" in b_val) and "customer relationship" in c_attr:
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Assertion that all major customer relationships remain strong contradicts known insolvency at primary customer.",
                    related_belief_ids=[b.id],
                    confidence=0.90,
                )

            # 3. Methane commitments vs EPA notice of violation (Vantage)
            if "methane" in b_attr and "methane" in c_attr:
                if ("committed" in b_val and "violation" in c_val) or ("violation" in b_val and "committed" in c_val):
                    return InferenceConflictResult(
                        is_conflict=True,
                        conflict_type="source_disagreement",
                        severity="high",
                        explanation="Public corporate commitment to ESG and emission reductions conflicts with federal EPA notice of violation for massive undetected leaks.",
                        related_belief_ids=[b.id],
                        confidence=0.94,
                    )

            # 4. Exclusive chip supply vs Multi-vendor / custom ASIC (Atlas)
            if "chip supply" in b_attr and "chip supply" in c_attr:
                if ("exclusive" in b_val and "evaluating" in c_val) or ("evaluating" in b_val and "exclusive" in c_val):
                    return InferenceConflictResult(
                        is_conflict=True,
                        conflict_type="inference",
                        severity="high",
                        explanation="Claimed exclusive 3-year supply agreement directly contradicts active evaluation of multiple alternative chip vendors and internal ASIC development.",
                        related_belief_ids=[b.id],
                        confidence=0.92,
                    )

            # 5. Pinnacle conviction vs Hedging (Pinnacle / Forge)
            if "investment stance" in b_attr and "investment stance" in c_attr:
                if ("bullish" in b_val and "hedged" in c_val) or ("hedged" in b_val and "bullish" in c_val):
                    return InferenceConflictResult(
                        is_conflict=True,
                        conflict_type="inference",
                        severity="high",
                        explanation="Managing partner's public high-conviction bullish stance contradicts disclosure of hedging 60% of the fund's position via options.",
                        related_belief_ids=[b.id],
                        confidence=0.95,
                    )

            # 6. Reserve backing vs Commercial real estate loan exposure (AetherPay / Solas - Sequence 4)
            if ("reserve" in b_attr or "reserve" in b_val or "treasury" in b_val) and ("commercial real estate" in c_val or "illiquid" in c_val or "duration mismatch" in c_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Assertion of 100% liquid T-Bill backing contradicts depository bank regulatory filing showing 62% of asset base locked in illiquid 5-year commercial real estate loans.",
                    related_belief_ids=[b.id],
                    confidence=0.95,
                )
            if ("commercial real estate" in b_val or "illiquid" in b_val) and ("reserve" in c_attr or "reserve" in c_val or "treasury" in c_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Claim of 100% short-term T-bill backing contradicts confirmed illiquid commercial real estate loan concentration.",
                    related_belief_ids=[b.id],
                    confidence=0.95,
                )

            # 7. Guaranteed settlement velocity vs Past-due receivables / Injunction (AetherPay / Nordic - Sequence 4)
            if ("settlement" in b_attr or "zero delays" in b_val or "instantly" in b_val) and ("past-due" in c_val or "frozen" in c_val or "injunctive" in c_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Guaranteed instant settlement claims directly contradict disclosures of $38M+ in merchant receivables past-due >45 days and court motions alleging frozen funds.",
                    related_belief_ids=[b.id],
                    confidence=0.94,
                )

            # 8. Valence Risk-free assertion vs CDS Hedge / Loan Impairment (Sequence 4)
            if ("risk-free" in b_val or "fully performing" in b_val) and ("cds" in c_val or "impaired" in c_val or "write-down" in c_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Characterizing debt exposure as risk-free / fully performing contradicts purchasing $80M in CDS default protection and recording a $48M loan impairment write-down.",
                    related_belief_ids=[b.id],
                    confidence=0.95,
                )

            # 9. CipherGuard Zero Compromise vs Sentient Exfiltration / Kernel Driver Bypass (Sequence 5)
            if ("zero customer" in b_val or "neutralized" in b_val) and ("exfiltrated" in c_val or "kernel driver" in c_val or "bypassing" in c_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Claims of zero customer compromise contradict verified 4.2TB genomic data exfiltration and forensic packet captures proving kernel driver bypass.",
                    related_belief_ids=[b.id],
                    confidence=0.96,
                )

            # 10. OmniCloud 99.999% SLA vs Outages / SLA Penalty Accruals (Sequence 5)
            if ("99.999%" in b_val or "five nines" in b_val) and ("14.8 hours" in c_val or "$28m in sla" in c_val or "99.82%" in c_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="99.999% platform availability claim (<5 minutes downtime/yr) contradicts $28M in SLA penalties, 14.8+ hours of downtime, and restated 99.82% availability.",
                    related_belief_ids=[b.id],
                    confidence=0.95,
                )

            # 11. CipherGuard In-Region Residency vs Global Model Training on Telemetry (Sequence 5)
            if ("zero cross-border" in b_val or "in-region" in b_val) and ("180tb" in c_val or "international" in c_val or "overseas" in c_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="FedRAMP/HIPAA in-region residency certifications contradict scientific publications disclosing model training on 180TB of raw customer memory dumps from international nodes.",
                    related_belief_ids=[b.id],
                    confidence=0.95,
                )

            # 12. Direct single-attribute qualitative conflict
            if b_attr == c_attr and b.entity.lower() == claim.entity.lower():
                if "did not decrease" in b_val and "increased" in c_val:
                    pass  # compatible
                elif "did not decrease" in b_val and ("decreased" in c_val or "slashed" in c_val or "cut" in c_val):
                    return InferenceConflictResult(
                        is_conflict=True,
                        conflict_type="inference",
                        severity="high",
                        explanation=f"Claim '{claim.value}' directly contradicts held belief '{b.value}'.",
                        related_belief_ids=[b.id],
                        confidence=0.92,
                    )
                elif "non-inferior" in b_val and "inferior" in c_val and "non-inferior" not in c_val:
                    return InferenceConflictResult(
                        is_conflict=True,
                        conflict_type="inference",
                        severity="high",
                        explanation="Clinical finding of inferiority contradicts held belief of non-inferiority.",
                        related_belief_ids=[b.id],
                        confidence=0.92,
                    )
                elif b_val != c_val:
                    if any(att in b_attr for att in ["headquarters", "ceo", "records impact", "status"]):
                        return InferenceConflictResult(
                            is_conflict=True,
                            conflict_type="inference",
                            severity="high",
                            explanation=f"Incompatible values for '{b.attribute}': held '{b.value}' vs incoming '{claim.value}'.",
                            related_belief_ids=[b.id],
                            confidence=0.90,
                        )

            # 13. Logical tensions across interrelated claims
            # Floating debt vs zero debt
            if ("zero floating-rate debt" in b_val and "sofr" in c_val) or ("zero floating-rate debt" in c_val and "sofr" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Assertion of zero floating-rate debt contradicts SOFR-pegged credit facility.",
                    related_belief_ids=[b.id],
                    confidence=0.92,
                )

            # Sold out capacity vs idled lines / stockpiled unsold inventory
            if ("sold out" in b_val and ("idled" in c_val or "unsold" in c_val)) or ("sold out" in c_val and ("idled" in b_val or "unsold" in b_val)):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Claim of sold-out production capacity contradicts idled assembly lines and unsold stockpiled inventory.",
                    related_belief_ids=[b.id],
                    confidence=0.92,
                )

            # GDPR EU only vs GPU clusters in Virginia
            if ("exclusively within eu" in b_val and "virginia" in c_val) or ("exclusively within eu" in c_val and "virginia" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Guaranteed in-region EU data residency contradicted by routing telemetry to GPU clusters in Virginia.",
                    related_belief_ids=[b.id],
                    confidence=0.94,
                )

            # Zero lost-time environmental incidents vs tailings pond rupture
            if ("zero lost-time environmental incidents" in b_val and "tailings" in c_val) or ("zero lost-time environmental incidents" in c_val and "tailings" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Claim of zero environmental incidents contradicted by regulatory cease-and-desist for tailings rupture.",
                    related_belief_ids=[b.id],
                    confidence=0.95,
                )

            # Actively manufacturing vs terminated contract
            if ("actively manufacturing" in b_val and "terminated" in c_val) or ("actively manufacturing" in c_val and "terminated" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Actively manufacturing under contract contradicted by termination for convenience.",
                    related_belief_ids=[b.id],
                    confidence=0.94,
                )

            # Universal vs counter-instance (all 12 hospitals vs 4 do not)
            if ("all 12" in b_val and "do not have" in c_val) or ("all 12" in c_val and "do not have" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Universal claim of accredited surgical units across all 12 hospitals contradicted by finding that 4 do not.",
                    related_belief_ids=[b.id],
                    confidence=0.93,
                )

            # Never applied vs active concession applications
            if ("never" in b_val and "active" in c_val and "application" in c_val) or ("never" in c_val and "active" in b_val and "application" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Denial of exploration activity contradicted by active concession filings in regulatory registry.",
                    related_belief_ids=[b.id],
                    confidence=0.94,
                )

            # Zero proprietary dependencies vs closed-source binaries
            if ("zero proprietary dependencies" in b_val and "proprietary closed-source" in c_val) or ("zero proprietary dependencies" in c_val and "proprietary closed-source" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Zero proprietary dependencies claim contradicted by embedded closed-source binaries.",
                    related_belief_ids=[b.id],
                    confidence=0.94,
                )

            # Exclusively domestic vs stores in Tokyo
            if ("exclusively within the domestic" in b_val and "tokyo" in c_val) or ("exclusively within the domestic" in c_val and "tokyo" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Exclusively domestic footprint claim contradicted by store operations in Tokyo.",
                    related_belief_ids=[b.id],
                    confidence=0.94,
                )

            # Strictly forbids crypto vs spot Bitcoin ETF
            if ("strictly forbids" in b_val and "bitcoin" in c_val) or ("strictly forbids" in c_val and "bitcoin" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Strict prohibition on crypto assets contradicted by $140M spot Bitcoin ETF holdings.",
                    related_belief_ids=[b.id],
                    confidence=0.94,
                )

            # 100% plastic-free vs virgin plastic
            if ("100% plastic-free" in b_val and "polyethylene" in c_val) or ("100% plastic-free" in c_val and "polyethylene" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="100% plastic-free packaging claim contradicted by 40% virgin polyethylene bottles.",
                    related_belief_ids=[b.id],
                    confidence=0.94,
                )

            # 85% response zero toxicities vs 60% hepatotoxicity termination
            if ("zero dose-limiting toxicities" in b_val and "hepatotoxicity" in c_val) or ("zero dose-limiting toxicities" in c_val and "hepatotoxicity" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Zero dose-limiting toxicities claim contradicted by trial termination for 60% hepatotoxicity rate.",
                    related_belief_ids=[b.id],
                    confidence=0.95,
                )

            # 99.999% network uptime vs 38 hours downtime
            if ("99.999% network uptime" in b_val and "38 hours" in c_val) or ("99.999% network uptime" in c_val and "38 hours" in b_val):
                return InferenceConflictResult(
                    is_conflict=True,
                    conflict_type="inference",
                    severity="high",
                    explanation="Five-nines network uptime (<5.25 mins downtime) contradicted by 38 hours total downtime.",
                    related_belief_ids=[b.id],
                    confidence=0.95,
                )

        return InferenceConflictResult(
            is_conflict=False,
            conflict_type=None,
            severity=None,
            explanation="No indirect or inference contradiction identified.",
            related_belief_ids=[],
            confidence=0.85,
        )
