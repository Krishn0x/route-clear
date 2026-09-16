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
  warnings?: string[];
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

// ── V2 types ──────────────────────────────────────────────────────────────────

export interface TransferRecord {
  transfer_id: string;
  total_amount: number;
  ordered_quantity: number;
  vendor_name: string;
  item_description: string;
}

export interface FieldAgreement {
  field: string;
  pass1_value?: number | boolean | null;
  pass2_value?: number | boolean | null;
  pass1_confidence: number;
  pass2_confidence: number;
  agreed: boolean;
  delta?: number | null;
}

export interface ComparisonResult {
  all_fields_agreed: boolean;
  disagreements: FieldAgreement[];
  agreements: FieldAgreement[];
  max_numeric_delta?: number | null;
  comparison_triggered_by: string[];
}

export interface ResolutionResult {
  resolved_accepted?: number | null;
  resolved_damaged?: number | null;
  resolved_rejected?: number | null;
  resolved_signature?: boolean | null;
  resolution_method: string;
  requires_human_review: boolean;
  human_review_reason?: string | null;
}

export interface VerificationResultSchema {
  pass2_triggered: boolean;
  pass2_trigger_reasons: string[];
  comparison_result?: ComparisonResult | null;
  resolution_result?: ResolutionResult | null;
  evidence_sufficient?: boolean | null;
  sufficiency_failures: string[];
}

// ── Document response ─────────────────────────────────────────────────────────

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
  // V2 field
  verification?: VerificationResultSchema | null;
}
