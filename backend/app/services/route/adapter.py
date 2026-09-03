import logging
import httpx
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.schemas.document import SettlementDecisionSchema, RouteActionResult, RouteActionState
from app.db.models import RouteAction
from app.core.config import settings
from app.services.route.converter import to_paise

logger = logging.getLogger(__name__)

class BaseRouteAdapter(ABC):
    def __init__(self):
        self.mode = "unknown"
        self.provider = "unknown"

    @abstractmethod
    async def _execute_reversal(self, transfer_id: str, amount: Decimal) -> Tuple[bool, Optional[str], Dict[str, Any], Optional[str]]:
        pass

    @abstractmethod
    async def _execute_release(self, transfer_id: str) -> Tuple[bool, Optional[str], Dict[str, Any], Optional[str]]:
        pass

    async def execute_settlement(self, db: Session, decision: SettlementDecisionSchema) -> List[RouteActionResult]:
        """
        Idempotent execution of Route actions with explicit state machine.
        """
        results = []
        
        # 1. Partial Reversal (if applicable)
        if decision.proposed_reversal_amount > Decimal('0'):
            rev_action_id = f"{decision.idempotency_key}_REVERSAL"
            rev_result = await self._run_action(
                db=db,
                action_id=rev_action_id,
                document_id=decision.document_id, 
                decision_id=decision.decision_id,
                transfer_id=decision.transfer_id,
                action_type="REVERSAL",
                amount=decision.proposed_reversal_amount
            )
            results.append(rev_result)
            
            # Stop if reversal fails
            if rev_result.status != RouteActionState.SUCCEEDED:
                return results

        # 2. Release Hold
        # Must execute release if auto approved
        rel_action_id = f"{decision.idempotency_key}_RELEASE"
        rel_result = await self._run_action(
            db=db,
            action_id=rel_action_id,
            document_id=decision.document_id,
            decision_id=decision.decision_id,
            transfer_id=decision.transfer_id,
            action_type="RELEASE",
            amount=decision.approved_release_amount
        )
        results.append(rel_result)
        
        return results

    async def _run_action(
        self, db: Session, action_id: str, document_id: str, decision_id: str, 
        transfer_id: str, action_type: str, amount: Decimal
    ) -> RouteActionResult:
        
        # Check existing state
        action = db.query(RouteAction).filter(RouteAction.id == action_id).first()
        
        if action:
            if action.state == RouteActionState.SUCCEEDED.value:
                return RouteActionResult(
                    action_id=action.id,
                    provider=self.provider,
                    mode=self.mode,
                    transfer_id=action.transfer_id,
                    action_type=action.action_type,
                    status=RouteActionState.SUCCEEDED,
                    external_id=action.external_id,
                    amount=action.amount,
                    response_metadata=action.provider_response or {},
                    executed_at=action.executed_at or datetime.utcnow()
                )
            elif action.state in [RouteActionState.EXECUTING.value, RouteActionState.RECONCILIATION_REQUIRED.value]:
                # Do NOT execute again if uncertain
                return RouteActionResult(
                    action_id=action.id,
                    provider=self.provider,
                    mode=self.mode,
                    transfer_id=action.transfer_id,
                    action_type=action.action_type,
                    status=RouteActionState.RECONCILIATION_REQUIRED,
                    amount=action.amount,
                    error="Action is stuck in EXECUTING state. Manual reconciliation required.",
                    executed_at=action.created_at
                )
            # If FAILED, we might retry, but let's be safe and just require reconciliation or manual intervention.
            # For this prototype, FAILED stays FAILED.
            if action.state == RouteActionState.FAILED.value:
                return RouteActionResult(
                    action_id=action.id,
                    provider=self.provider,
                    mode=self.mode,
                    transfer_id=action.transfer_id,
                    action_type=action.action_type,
                    status=RouteActionState.FAILED,
                    amount=action.amount,
                    error=action.error,
                    executed_at=action.created_at
                )
        else:
            # Create PENDING/EXECUTING action
            action = RouteAction(
                id=action_id,
                document_id=document_id,
                decision_id=decision_id,
                transfer_id=transfer_id,
                action_type=action_type,
                state=RouteActionState.EXECUTING.value,
                amount=amount
            )
            db.add(action)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                # Concurrent execution protection
                return RouteActionResult(
                    action_id=action_id, provider=self.provider, mode=self.mode,
                    transfer_id=transfer_id, action_type=action_type,
                    status=RouteActionState.RECONCILIATION_REQUIRED, amount=amount,
                    error="Concurrent execution detected.", executed_at=datetime.utcnow()
                )

        # Execute
        try:
            if action_type == "REVERSAL":
                success, ext_id, resp, err = await self._execute_reversal(transfer_id, amount)
            else:
                success, ext_id, resp, err = await self._execute_release(transfer_id)
                
            action.state = RouteActionState.SUCCEEDED.value if success else RouteActionState.FAILED.value
            action.external_id = ext_id
            action.provider_response = resp
            action.error = err
            action.executed_at = datetime.utcnow()
            
        except httpx.TimeoutException:
            action.state = RouteActionState.RECONCILIATION_REQUIRED.value
            action.error = "API Timeout. Execution uncertain."
        except httpx.HTTPError as e:
            action.state = RouteActionState.RECONCILIATION_REQUIRED.value
            action.error = f"API Error. Execution uncertain: {str(e)}"
        except Exception as e:
            action.state = RouteActionState.FAILED.value
            action.error = f"Unexpected failure: {str(e)}"
            
        db.commit()
        db.refresh(action)
        
        return RouteActionResult(
            action_id=action.id,
            provider=self.provider,
            mode=self.mode,
            transfer_id=action.transfer_id,
            action_type=action.action_type,
            status=RouteActionState(action.state),
            external_id=action.external_id,
            amount=action.amount,
            response_metadata=action.provider_response or {},
            error=action.error,
            executed_at=action.executed_at or datetime.utcnow()
        )

from typing import Tuple

class SimulatedRouteAdapter(BaseRouteAdapter):
    def __init__(self):
        super().__init__()
        self.mode = "simulated"
        self.provider = "mock"

    async def _execute_reversal(self, transfer_id: str, amount: Decimal) -> Tuple[bool, Optional[str], Dict[str, Any], Optional[str]]:
        logger.info(f"[SIMULATED] Reversing {amount} for {transfer_id}")
        
        # Simulated failure cases for testing
        if amount == Decimal("999.99"):
            return False, None, {}, "Simulated provider failure"
        if amount == Decimal("888.88"):
            raise httpx.TimeoutException("Simulated timeout")
            
        return True, f"sim_rev_{transfer_id}", {"simulated": True, "amount": str(amount)}, None

    async def _execute_release(self, transfer_id: str) -> Tuple[bool, Optional[str], Dict[str, Any], Optional[str]]:
        logger.info(f"[SIMULATED] Releasing hold for {transfer_id}")
        
        if transfer_id == "tr_fail_release":
            return False, None, {}, "Simulated release failure"
            
        return True, None, {"simulated": True, "on_hold": False}, None


class RazorpayRouteAdapter(BaseRouteAdapter):
    def __init__(self):
        super().__init__()
        self.mode = settings.ROUTE_MODE.lower()
        self.provider = "razorpay"
        self.key_id = settings.RAZORPAY_KEY_ID
        self.key_secret = settings.RAZORPAY_KEY_SECRET
        self.base_url = "https://api.razorpay.com/v1"
        if not self.key_id or not self.key_secret:
            raise ValueError("Razorpay credentials missing")
        if self.mode not in ["sandbox", "live"]:
            raise ValueError("RazorpayRouteAdapter requires mode to be sandbox or live")

    async def _execute_reversal(self, transfer_id: str, amount: Decimal) -> Tuple[bool, Optional[str], Dict[str, Any], Optional[str]]:
        paise = to_paise(amount)
        async with httpx.AsyncClient(auth=(self.key_id, self.key_secret)) as client:
            resp = await client.post(
                f"{self.base_url}/transfers/{transfer_id}/reversals",
                json={"amount": paise}
            )
            if resp.status_code >= 500:
                raise httpx.HTTPError(f"HTTP {resp.status_code} Server Error: {resp.text}")
            if resp.status_code >= 400:
                return False, None, resp.json() if resp.text else {}, f"HTTP {resp.status_code}: {resp.text}"
            data = resp.json()
            return True, data.get("id"), data, None

    async def _execute_release(self, transfer_id: str) -> Tuple[bool, Optional[str], Dict[str, Any], Optional[str]]:
        async with httpx.AsyncClient(auth=(self.key_id, self.key_secret)) as client:
            # Documented boolean parameter
            resp = await client.patch(
                f"{self.base_url}/transfers/{transfer_id}",
                json={"on_hold": False}
            )
            if resp.status_code >= 500:
                raise httpx.HTTPError(f"HTTP {resp.status_code} Server Error: {resp.text}")
            if resp.status_code >= 400:
                return False, None, resp.json() if resp.text else {}, f"HTTP {resp.status_code}: {resp.text}"
            data = resp.json()
            return True, data.get("id"), data, None

def get_route_adapter() -> BaseRouteAdapter:
    mode = settings.ROUTE_MODE.lower()
    if mode in ["sandbox", "live"]:
        return RazorpayRouteAdapter()
    return SimulatedRouteAdapter()
