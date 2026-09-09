from datetime import datetime, timezone
from jnaara.belief.manager import BeliefManager
from jnaara.db.repository import Repository
from jnaara.models.domain import Fact


def test_belief_lifecycle_creation_and_resolution(
    manager: BeliefManager, repository: Repository, sample_fact_e1: Fact, sample_fact_e7: Fact
):
    # 1. Process E1 (Initial revenue = $480M)
    res1 = manager.process_fact(sample_fact_e1)
    assert not res1.skipped
    assert len(res1.claims) > 0

    beliefs = repository.get_beliefs_for_entity("NovaTech")
    assert len(beliefs) == 1
    assert beliefs[0].value == "$480M"
    assert beliefs[0].version == 1

    # 2. Process E7 (Restatement to $412M)
    res2 = manager.process_fact(sample_fact_e7)
    assert not res2.skipped

    # Verify conflict was logged
    conflicts = repository.get_conflicts("NovaTech")
    assert len(conflicts) == 1
    assert conflicts[0].conflict_type == "direct"
    assert conflicts[0].resolution is not None

    # Under recency, E7 wins
    updated_belief = repository.get_belief(beliefs[0].id)
    assert updated_belief is not None
    assert updated_belief.value == "$412M"
    assert updated_belief.version == 2
    assert "E1" in updated_belief.contradicting_fact_ids
    assert "E7" in updated_belief.supporting_fact_ids


def test_idempotent_ingestion(manager: BeliefManager, sample_fact_e1: Fact):
    res1 = manager.process_fact(sample_fact_e1)
    assert not res1.skipped

    # Re-ingest exact same fact ID
    res2 = manager.process_fact(sample_fact_e1)
    assert res2.skipped


def test_provenance_chain_retrieval(
    manager: BeliefManager, repository: Repository, sample_fact_e1: Fact, sample_fact_e7: Fact
):
    manager.process_fact(sample_fact_e1)
    manager.process_fact(sample_fact_e7)

    beliefs = repository.get_beliefs_for_entity("NovaTech")
    belief = beliefs[0]

    chain = repository.get_provenance_chain(belief.id)
    assert chain.belief.id == belief.id
    assert len(chain.history) == 2  # v1 creation + v2 update
    assert len(chain.supporting_facts) == 1
    assert chain.supporting_facts[0].id == "E7"
    assert len(chain.contradicting_facts) == 1
    assert chain.contradicting_facts[0].id == "E1"
    assert len(chain.conflicts) == 1
    assert len(chain.resolutions) == 1
