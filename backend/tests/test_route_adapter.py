import pytest
from decimal import Decimal
import uuid
from app.services.route.adapter import SimulatedRouteAdapter
from app.schemas.document import SettlementDecisionSchema
from app.db.models import RouteAction
from app.schemas.document import RouteActionState

# Need an in-memory DB for adapter testing
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.session import Base

test_engine = create_engine(
    "sqlite://", 
    connect_args={"check_same_thread": False}, 
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)

@pytest.mark.asyncio
async def test_simulated_adapter_reversal_and_release():
    db = TestingSessionLocal()
    adapter = SimulatedRouteAdapter()
    decision = SettlementDecisionSchema(
        document_id=str(uuid.uuid4()),
        decision_id=str(uuid.uuid4()),
        transfer_id="tr_sim_123",
        approved_release_amount=Decimal("90000.00"),
        proposed_reversal_amount=Decimal("10000.00"),
        requires_human_review=False,
        policy_version="1.0",
        idempotency_key="tr_sim_123_AUTO"
    )
    
    results = await adapter.execute_settlement(db, decision)
    assert len(results) == 2
    
    rev = results[0]
    assert rev.status == RouteActionState.SUCCEEDED
    assert rev.action_type == "REVERSAL"
    assert rev.amount == Decimal("10000.00")
    
    rel = results[1]
    assert rel.status == RouteActionState.SUCCEEDED
    assert rel.action_type == "RELEASE"
    assert rel.amount == Decimal("90000.00")
    # Verify DB linkage
    action_in_db = db.query(RouteAction).filter(RouteAction.id == rev.action_id).first()
    assert action_in_db.document_id == decision.document_id
    assert action_in_db.decision_id == decision.decision_id
    
    # Try duplicate execution
    results2 = await adapter.execute_settlement(db, decision)
    assert len(results2) == 2
    assert results2[0].status == RouteActionState.SUCCEEDED
    assert results2[0].executed_at == rev.executed_at # Should return existing execution time

@pytest.mark.asyncio
async def test_simulated_timeout_reconciliation():
    db = TestingSessionLocal()
    adapter = SimulatedRouteAdapter()
    decision = SettlementDecisionSchema(
        document_id=str(uuid.uuid4()),
        decision_id=str(uuid.uuid4()),
        transfer_id="tr_sim_999",
        approved_release_amount=Decimal("0.00"),
        proposed_reversal_amount=Decimal("888.88"), # Simulated timeout value
        requires_human_review=False,
        policy_version="1.0",
        idempotency_key="tr_sim_999_AUTO"
    )
    
    results = await adapter.execute_settlement(db, decision)
    assert len(results) == 1 # stopped at reversal
    assert results[0].status == RouteActionState.RECONCILIATION_REQUIRED
    
    # Try duplicate execution (Should not execute blindly)
    results2 = await adapter.execute_settlement(db, decision)
    assert results2[0].status == RouteActionState.RECONCILIATION_REQUIRED
    assert "Manual reconciliation required" in results2[0].error

