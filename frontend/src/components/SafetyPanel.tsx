import { useState } from 'react';
import { apiClient } from '../apiClient';
import { DocumentResponse } from '../types';
import { ShieldCheck, ShieldAlert, Cpu, Activity, User, Hash } from 'lucide-react';

interface Props {
  doc: DocumentResponse;
  onUpdate: (doc: DocumentResponse) => void;
}

export default function SafetyPanel({ doc, onUpdate }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form states strictly for quantity (Backend rules!)
  const [acceptedQty, setAcceptedQty] = useState<string>('');
  const [damagedQty, setDamagedQty] = useState<string>('');
  const [rejectedQty, setRejectedQty] = useState<string>('');

  const submitProcess = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.post(`/api/documents/${doc.id}/process`);
      onUpdate(res.data);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Processing failed');
    } finally {
      setLoading(false);
    }
  };

  const submitHumanReview = async () => {
    setLoading(true);
    setError(null);
    try {
      await apiClient.post(`/api/documents/${doc.id}/human-review`, {
        accepted_quantity: parseInt(acceptedQty) || 0,
        damaged_quantity: parseInt(damagedQty) || 0,
        rejected_quantity: parseInt(rejectedQty) || 0
      });
      // Fetch updated
      const res = await apiClient.get(`/api/documents/${doc.id}`);
      onUpdate(res.data);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Review failed');
    } finally {
      setLoading(false);
    }
  };

  const renderStatusBanner = () => {
    if (doc.status === 'PENDING') {
      return (
        <div className="bg-bg-elevated border border-border-default rounded p-4 mb-4 flex justify-between items-center">
          <div>
            <div className="font-mono text-sm text-text-primary tracking-widest font-bold uppercase">Evidence Received</div>
            <div className="text-xs text-text-secondary mt-1">Awaiting verification pipeline execution.</div>
          </div>
          <button onClick={submitProcess} disabled={loading} className="bg-accent text-white px-4 py-2 text-xs font-bold uppercase tracking-wider rounded hover:bg-accent/90 disabled:opacity-50">
            {loading ? 'Executing...' : 'Execute Pipeline'}
          </button>
        </div>
      );
    }

    if (doc.status === 'COMPLETED' || doc.status === 'PROCESSED') {
      const passed = doc.validation?.passed;
      if (passed) {
        return (
          <div className="bg-status-safe/10 border border-status-safe/30 rounded p-4 mb-4">
            <div className="flex items-center text-status-safe font-bold font-mono tracking-widest text-lg mb-1">
              <ShieldCheck className="w-5 h-5 mr-2" /> ROUTE CLEARED
            </div>
            <div className="text-status-safe/80 text-xs font-mono">
              Deterministic safety checks passed. Route action executed.
            </div>
          </div>
        );
      }
    }

    if (doc.status === 'HUMAN_REVIEW') {
      return (
        <div className="bg-status-review/10 border border-status-review/30 rounded p-4 mb-4">
          <div className="flex items-center text-status-review font-bold font-mono tracking-widest text-lg mb-1">
            <User className="w-5 h-5 mr-2" /> HUMAN REVIEW REQUIRED
          </div>
          <div className="text-status-review/80 text-xs font-mono mt-2 space-y-1">
            {doc.validation?.failure_reasons.map((r, i) => (
              <div key={i}>• {r}</div>
            ))}
            {doc.verification?.sufficiency_failures.map((r, i) => (
              <div key={i}>• {r}</div>
            ))}
          </div>
        </div>
      );
    }

    if (doc.status === 'FAILED') {
      return (
        <div className="bg-status-failed/10 border border-status-failed/30 rounded p-4 mb-4">
          <div className="flex items-center text-status-failed font-bold font-mono tracking-widest text-lg mb-1">
            <ShieldAlert className="w-5 h-5 mr-2" /> SAFETY BLOCKED
          </div>
          <div className="text-status-failed/80 text-xs font-mono mt-1">
            Pipeline aborted due to critical error.
          </div>
        </div>
      );
    }
  };

  return (
    <div className="bg-bg-surface border border-border-default rounded-md h-full flex flex-col overflow-hidden font-mono text-sm">
      <div className="p-4 border-b border-border-default bg-bg-elevated flex justify-between items-center">
        <h3 className="font-bold text-text-primary uppercase tracking-widest">Pipeline Console</h3>
        <span className="text-xs text-text-secondary">Trf: <span className="text-text-primary">{doc.transfer_id}</span></span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {error && (
          <div className="p-3 bg-status-failed/10 border border-status-failed/30 text-status-failed text-xs rounded mb-4">
            {error}
          </div>
        )}

        {renderStatusBanner()}

        {doc.verification && (
          <div className="border border-border-default rounded bg-bg-base overflow-hidden">
            <div className="bg-bg-elevated p-2 text-xs font-bold border-b border-border-default flex items-center text-text-secondary tracking-widest">
              <Cpu className="w-4 h-4 mr-2" /> VLM Evidence Extraction
            </div>
            
            <div className="p-3 space-y-4 text-xs">
              {/* Comparison Results */}
              {doc.verification.comparison_result && (
                <div>
                  <div className="text-[10px] text-text-secondary uppercase mb-2">Dual-Pass Comparator (Deterministic)</div>
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-border-default text-text-secondary">
                        <th className="pb-1 font-normal">Field</th>
                        <th className="pb-1 font-normal">AI Pass 1</th>
                        <th className="pb-1 font-normal">AI Pass 2</th>
                        <th className="pb-1 font-normal">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...doc.verification.comparison_result.agreements, ...doc.verification.comparison_result.disagreements].map((row, idx) => (
                        <tr key={idx} className="border-b border-border-default/50 last:border-0">
                          <td className="py-2 text-text-secondary capitalize">{row.field.replace('_', ' ')}</td>
                          <td className="py-2 text-text-primary">{String(row.pass1_value ?? 'N/A')} <span className="text-[9px] text-text-secondary ml-1">({(row.pass1_confidence*100).toFixed(0)}%)</span></td>
                          <td className="py-2 text-text-primary">{String(row.pass2_value ?? 'N/A')} <span className="text-[9px] text-text-secondary ml-1">({(row.pass2_confidence*100).toFixed(0)}%)</span></td>
                          <td className="py-2">
                            {row.agreed ? (
                              <span className="text-status-safe font-bold">MATCH</span>
                            ) : (
                              <span className="text-status-failed font-bold">CONFLICT</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {doc.validation && (
          <div className="border border-border-default rounded bg-bg-base overflow-hidden">
             <div className="bg-bg-elevated p-2 text-xs font-bold border-b border-border-default flex items-center text-text-secondary tracking-widest">
              <Activity className="w-4 h-4 mr-2" /> Deterministic Safety Engine
            </div>
            <div className="p-3 text-xs space-y-2">
              <div className="flex justify-between items-center border-b border-border-default/50 pb-2">
                <span className="text-text-secondary">Quantity Reconciliation</span>
                <span className="text-text-primary">
                  {doc.ordered_quantity} = ({doc.evidence?.extracted_fields.accepted_quantity?.value ?? 0} + {doc.evidence?.extracted_fields.damaged_quantity?.value ?? 0} + {doc.evidence?.extracted_fields.rejected_quantity?.value ?? 0})
                </span>
              </div>
              <div className="flex justify-between items-center border-b border-border-default/50 pb-2">
                <span className="text-text-secondary">Unaccounted Quantity</span>
                <span className={doc.validation.unaccounted_quantity === 0 ? "text-status-safe font-bold" : "text-status-failed font-bold"}>
                  {doc.validation.unaccounted_quantity}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-text-secondary">Signature Verification</span>
                <span className={doc.evidence?.extracted_fields.signature_present?.value ? "text-status-safe font-bold" : "text-status-failed font-bold"}>
                  {doc.evidence?.extracted_fields.signature_present?.value ? "PRESENT" : "MISSING"}
                </span>
              </div>
            </div>
          </div>
        )}

        {doc.decision && (
           <div className="border border-border-default rounded bg-bg-base overflow-hidden">
             <div className="bg-bg-elevated p-2 text-xs font-bold border-b border-border-default flex items-center text-text-secondary tracking-widest">
              <ShieldCheck className="w-4 h-4 mr-2" /> Settlement Decision Math
            </div>
            <div className="p-3 text-xs space-y-2">
               <div className="flex justify-between">
                <span className="text-text-secondary">Proposed Reversal</span>
                <span className="text-status-failed">₹{doc.decision.proposed_reversal_amount.toFixed(2)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-text-secondary">Approved Release</span>
                <span className="text-status-safe">₹{doc.decision.approved_release_amount.toFixed(2)}</span>
              </div>
            </div>
          </div>
        )}

        {doc.status === 'HUMAN_REVIEW' && (
          <div className="border border-status-review rounded bg-bg-base overflow-hidden mt-4">
             <div className="bg-status-review/10 p-3 text-xs font-bold border-b border-status-review/30 flex items-center text-status-review tracking-widest">
              <User className="w-4 h-4 mr-2" /> Human Review Required
            </div>
            <div className="p-4 space-y-4 text-xs">
              <div className="text-text-primary leading-relaxed bg-bg-elevated p-3 border border-border-default rounded">
                <p className="font-bold mb-2">Safety Constraint:</p>
                <p className="text-status-review mb-2">Enter the verified QUANTITY directly from the physical document.</p>
                <p className="text-text-secondary italic text-[10px]">Do not enter a financial amount. Settlement math is calculated safely server-side.</p>
              </div>
              
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-[10px] text-text-secondary uppercase mb-1">Accepted Qty</label>
                  <input type="number" value={acceptedQty} onChange={e => setAcceptedQty(e.target.value)} className="w-full bg-bg-surface border border-border-default rounded p-2 text-text-primary focus:border-accent outline-none" min="0" />
                </div>
                <div>
                  <label className="block text-[10px] text-text-secondary uppercase mb-1">Damaged Qty</label>
                  <input type="number" value={damagedQty} onChange={e => setDamagedQty(e.target.value)} className="w-full bg-bg-surface border border-border-default rounded p-2 text-text-primary focus:border-accent outline-none" min="0" />
                </div>
                <div>
                  <label className="block text-[10px] text-text-secondary uppercase mb-1">Rejected Qty</label>
                  <input type="number" value={rejectedQty} onChange={e => setRejectedQty(e.target.value)} className="w-full bg-bg-surface border border-border-default rounded p-2 text-text-primary focus:border-accent outline-none" min="0" />
                </div>
              </div>
              <button onClick={submitHumanReview} disabled={loading} className="w-full bg-status-review text-bg-base font-bold tracking-widest uppercase py-2 rounded hover:bg-status-review/90 disabled:opacity-50">
                {loading ? 'Submitting...' : 'Submit Quantities'}
              </button>
            </div>
          </div>
        )}

        {doc.audit_logs && doc.audit_logs.length > 0 && (
          <div className="border border-border-default rounded bg-bg-base overflow-hidden mt-4">
             <div className="bg-bg-elevated p-2 text-xs font-bold border-b border-border-default flex items-center text-text-secondary tracking-widest">
              <Hash className="w-4 h-4 mr-2" /> Append-only Audit Trail
            </div>
            <div className="p-3 text-[10px] text-text-secondary italic border-b border-border-default/50">
              Each record is strictly linked to the previous record by cryptographic hash.
            </div>
            <div className="p-3 space-y-3">
              {doc.audit_logs.map((log, idx) => (
                <div key={idx} className="relative pl-4 border-l border-border-default/50 before:absolute before:w-2 before:h-2 before:bg-bg-elevated before:border before:border-border-default before:rounded-full before:-left-[4.5px] before:top-1.5">
                  <div className="flex justify-between items-baseline mb-1">
                    <span className="font-bold text-accent">{log.event_type}</span>
                    <span className="text-text-secondary">{new Date(log.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className="bg-bg-elevated p-2 rounded border border-border-default/30 text-text-primary overflow-x-auto whitespace-pre-wrap mt-1">
                    {JSON.stringify(log.details, null, 2)}
                  </div>
                  <div className="mt-1 flex items-center text-[9px] text-text-secondary font-mono break-all bg-bg-base/50 p-1 rounded">
                    <Hash className="w-3 h-3 mr-1 inline-block text-border-default" /> 
                    {log.event_hash}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
