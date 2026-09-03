export interface Box2D {
  xmin: number;
  ymin: number;
  xmax: number;
  ymax: number;
}

export interface FieldEvidence<T> {
  value: T;
  confidence: number;
  evidence_note?: string;
  evidence_region?: Box2D;
}

export interface FulfillmentFields {
  accepted_quantity?: FieldEvidence<number>;
  damaged_quantity?: FieldEvidence<number>;
  rejected_quantity?: FieldEvidence<number>;
  signature_present?: FieldEvidence<boolean>;
  correction_detected?: FieldEvidence<boolean>;
}

export interface FulfillmentEvidenceSchema {
  provider: string;
  model_identifier: string;
  overall_confidence: number;
  extracted_fields: FulfillmentFields;
}

export interface SafetyValidationResult {
  passed: boolean;
  failure_reasons: string[];
  unaccounted_quantity: number;
}

export interface SettlementDecisionSchema {
  transfer_id: string;
  approved_release_amount: number;
  proposed_reversal_amount: number;
  requires_human_review: boolean;
  policy_version: string;
  idempotency_key: string;
}

export interface DocumentResponse {
  id: string;
  filename: string;
  status: 'PENDING' | 'PROCESSED' | 'HUMAN_REVIEW' | 'FAILED' | 'COMPLETED';
  transfer_id: string;
  total_amount: number;
  ordered_quantity: number;
  evidence?: FulfillmentEvidenceSchema;
  validation?: SafetyValidationResult;
  decision?: SettlementDecisionSchema;
  audit_logs: any[];
  policy_math?: {
    reversal_percentage: number;
    maximum_auto_reversal_percentage: number;
  };
}
