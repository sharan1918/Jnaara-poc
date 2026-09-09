from pathlib import Path
from jnaara.belief.manager import BeliefManager
from jnaara.conflict.detector import ConflictDetector
from jnaara.conflict.resolver import ConflictResolver
from jnaara.db.repository import Repository
from jnaara.ingestion.ingestor import FactIngestor


def test_sequence_1_easy_integration(
    manager: BeliefManager, repository: Repository, dataset_path: Path
):
    ingestor = FactIngestor()
    facts = ingestor.load_sequence(dataset_path, "sequence_1_easy")
    assert len(facts) == 27

    results = manager.process_sequence(facts)
    assert len(results) == 27

    # 1. Assert NovaTech revenue conflict detected and resolved
    conflicts = repository.get_conflicts("NovaTech")
    assert any(c.conflict_type == "direct" and "revenue" in c.attribute.lower() for c in conflicts)

    # Final revenue belief should be $412M (from SEC Restatement E7)
    revenue_belief = repository.get_belief_by_entity_attribute("NovaTech", "Q4 2024 revenue")
    assert revenue_belief is not None
    assert "$412M" in revenue_belief.value

    # 2. Assert Meridian Healthcare hospital count conflict detected
    meridian_conflicts = repository.get_conflicts("Meridian Healthcare")
    assert any("hospital" in c.attribute.lower() for c in meridian_conflicts)
    hospital_belief = repository.get_belief_by_entity_attribute("Meridian Healthcare", "operational hospitals")
    assert hospital_belief is not None
    # E17 reduced it to 134
    assert "134" in hospital_belief.value

    # 3. Assert Meridian Healthcare net income conflict detected
    assert any("net income" in c.attribute.lower() for c in meridian_conflicts)
    net_income_belief = repository.get_belief_by_entity_attribute("Meridian Healthcare", "FY2024 net income")
    assert net_income_belief is not None
    assert "$131M" in net_income_belief.value

    # 5. Customer count progression
    cust_conflicts = [c for c in conflicts if "customer" in c.attribute.lower()]
    assert len(cust_conflicts) > 0
    cust_belief = repository.get_belief_by_entity_attribute("NovaTech", "enterprise customers")
    assert cust_belief is not None
    # Under recency, E26 (298 verified customers) is the latest update
    assert "298" in cust_belief.value


def test_sequence_2_medium_integration(
    manager: BeliefManager, repository: Repository, dataset_path: Path
):
    ingestor = FactIngestor()
    facts = ingestor.load_sequence(dataset_path, "sequence_2_medium")
    assert len(facts) == 27

    results = manager.process_sequence(facts)
    assert len(results) == 27

    all_conflicts = repository.get_conflicts()
    assert len(all_conflicts) > 0

    # 1. Arcadia vs TerraMotors cross-entity inference conflict
    arcadia_conflicts = repository.get_conflicts("Arcadia Robotics")
    assert any("customer relationship" in c.attribute.lower() for c in arcadia_conflicts)

    # 2. Vantage ESG vs EPA violation source disagreement
    vantage_conflicts = repository.get_conflicts("Vantage Energy")
    assert any("methane" in c.attribute.lower() for c in vantage_conflicts)

    # 3. Arcadia revenue guidance miss
    assert any("revenue" in c.attribute.lower() for c in arcadia_conflicts)


def test_sequence_3_hard_integration(
    manager: BeliefManager, repository: Repository, dataset_path: Path
):
    ingestor = FactIngestor()
    facts = ingestor.load_sequence(dataset_path, "sequence_3_hard")
    assert len(facts) == 30

    results = manager.process_sequence(facts)
    assert len(results) == 30

    all_conflicts = repository.get_conflicts()
    assert len(all_conflicts) > 0

    # 1. Capacity constrained vs Inventory jump (Helios)
    helios_conflicts = repository.get_conflicts("Helios Semiconductor")
    assert any("capacity" in c.description.lower() or "inventory" in c.description.lower() for c in helios_conflicts)

    # 2. Exclusive supply agreement vs alternative vendors (Atlas Cloud)
    atlas_conflicts = repository.get_conflicts("Atlas Cloud Systems")
    assert any("chip supply" in c.attribute.lower() for c in atlas_conflicts)

    # 3. FT-400 efficacy quantitative delta (Forge Therapeutics)
    forge_conflicts = repository.get_conflicts("Forge Therapeutics")
    assert any("ft-400" in c.attribute.lower() for c in forge_conflicts)

    # 4. Pinnacle conviction vs hedging (Pinnacle Ventures)
    pinnacle_conflicts = repository.get_conflicts("Pinnacle Ventures")
    assert any("investment stance" in c.attribute.lower() for c in pinnacle_conflicts)


def test_strategy_switching_produces_different_outcomes(
    repository: Repository, dataset_path: Path, analyzer, detector
):
    ingestor = FactIngestor()
    facts = ingestor.load_sequence(dataset_path, "sequence_1_easy")

    # Run with recency
    resolver_recency = ConflictResolver("recency")
    mgr_recency = BeliefManager(repository, analyzer, detector, resolver_recency)
    mgr_recency.process_sequence(facts)
    recency_cust_belief = repository.get_belief_by_entity_attribute("NovaTech", "enterprise customers")
    assert recency_cust_belief is not None
    recency_val = recency_cust_belief.value

    # Reset repository
    repository.clear_all()

    # Run with corroboration
    resolver_corrob = ConflictResolver("corroboration")
    detector_corrob = ConflictDetector(repository, analyzer)
    mgr_corrob = BeliefManager(repository, analyzer, detector_corrob, resolver_corrob)
    mgr_corrob.process_sequence(facts)
    corrob_cust_belief = repository.get_belief_by_entity_attribute("NovaTech", "enterprise customers")
    assert corrob_cust_belief is not None
    corrob_val = corrob_cust_belief.value

    # Under corroboration, earlier facts with multiple high-reliability sources (E4+E10 = 340)
    # outscore a single later claim (E26 = 298), producing a different outcome!
    assert recency_val == "298"
    assert corrob_val == "340"
    assert recency_val != corrob_val
