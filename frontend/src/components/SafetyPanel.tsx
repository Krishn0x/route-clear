import { useState } from 'react';
import axios from 'axios';
import { DocumentResponse } from '../types';
import { CheckCircle, AlertTriangle, Play } from 'lucide-react';

interface Props {
  doc: DocumentResponse;
  onUpdate: (doc: DocumentResponse) => void;
}

export default function SafetyPanel({ doc, onUpdate }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [releaseAmt, setReleaseAmt] = useState('');
  const [reversalAmt, setReversalAmt] = useState('');

  const processDoc = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.post(`/api/documents/${doc.id}/process`);
      onUpdate(res.data);
    } catch (err: any) {
      console.error(err);
      if (err.response?.status === 429) {
        setError("Document processing is temporarily unavailable because the AI provider quota has been reached. No financial action was executed.");
      } else if (err.message === 'Network Error' || err.code === 'ECONNABORTED') {
        setError("Unable to reach the processing service. No financial action was executed.");
      } else if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Document processing failed. No financial action was executed.");
      }
    } finally {
      setLoading(false);
    }
  };

  const submitHumanReview = async () => {
    setLoading(true);
    setError(null);
    try {
      await axios.post(`/api/documents/${doc.id}/human-review`, null, {
        params: {
          approved_release_amount: releaseAmt,
          proposed_reversal_amount: reversalAmt
        }
      });
      // Fetch updated
      const res = await axios.get(`/api/documents/${doc.id}`);
      onUpdate(res.data);
    } catch (err: any) {
      console.error(err);
      if (err.response?.data?.detail) {
        setError(err.response.data.detail);
      } else {
        setError("Validation failed. No financial action was executed.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white shadow rounded-lg p-4 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-lg font-medium text-gray-900">Safety & Settlement</h3>
        <span className={`px-2 py-1 rounded text-xs font-semibold ${
          doc.status === 'COMPLETED' ? 'bg-green-100 text-green-800' :
          doc.status === 'FAILED' ? 'bg-red-100 text-red-800' :
          doc.status === 'HUMAN_REVIEW' ? 'bg-yellow-100 text-yellow-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {doc.status}
        </span>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-100 border border-red-300 rounded text-sm text-red-800 flex items-start">
          <AlertTriangle className="w-5 h-5 mr-2 flex-shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {doc.status === 'PENDING' && (
        <div className="mt-4 flex-1 flex flex-col items-center justify-center border-2 border-dashed rounded p-4">
          <p className="text-sm text-gray-500 text-center mb-4">Document uploaded. Ready for AI Extraction and Safety Validation.</p>
          <button
            onClick={processDoc}
            disabled={loading}
            className="flex items-center px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 disabled:opacity-50"
          >
            <Play className="w-4 h-4 mr-2" />
            {loading ? 'Processing...' : 'Run Process'}
          </button>
        </div>
      )}

      {doc.evidence && (
        <div className="space-y-4 flex-1 overflow-y-auto">
          <div className="bg-gray-50 p-3 rounded">
            <h4 className="text-sm font-semibold text-gray-700 mb-2">VLM Extraction</h4>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>Ordered: <span className="font-mono">{doc.ordered_quantity}</span></div>
              <div>Accepted: {doc.evidence.extracted_fields.accepted_quantity?.value == null ? <span className="text-red-500 italic">Missing / unreadable</span> : <span className="font-mono">{doc.evidence.extracted_fields.accepted_quantity.value}</span>}</div>
              <div>Damaged: {doc.evidence.extracted_fields.damaged_quantity?.value == null ? <span className="text-red-500 italic">Missing / unreadable</span> : <span className="font-mono">{doc.evidence.extracted_fields.damaged_quantity.value}</span>}</div>
              <div>Rejected: {doc.evidence.extracted_fields.rejected_quantity?.value == null ? <span className="text-red-500 italic">Missing / unreadable</span> : <span className="font-mono">{doc.evidence.extracted_fields.rejected_quantity.value}</span>}</div>
            </div>
          </div>

          {doc.validation && (
            <div className={`p-3 rounded border ${doc.validation.passed ? 'border-green-200 bg-green-50' : 'border-red-200 bg-red-50'}`}>
              <h4 className="text-sm font-semibold flex items-center mb-2">
                {doc.validation.passed ? <CheckCircle className="w-4 h-4 text-green-600 mr-1" /> : <AlertTriangle className="w-4 h-4 text-red-600 mr-1" />}
                Deterministic Safety Engine
              </h4>
              <div className="text-xs text-gray-700 space-y-1">
                {doc.decision && (
                  <>
                    <div>Reversal: <span className="font-mono">₹{doc.decision.proposed_reversal_amount}</span></div>
                    {doc.policy_math && (
                      <>
                        <div>Reversal percentage: <span className="font-mono">{doc.policy_math.reversal_percentage.toFixed(2)}%</span></div>
                        <div>Automatic reversal limit: <span className="font-mono">{doc.policy_math.maximum_auto_reversal_percentage.toFixed(2)}%</span></div>
                      </>
                    )}
                  </>
                )}
                
                <div>Quantity reconciliation: 
                  <span className="font-mono ml-1">
                    {doc.ordered_quantity} − ({doc.evidence.extracted_fields.accepted_quantity?.value ?? 0} + {doc.evidence.extracted_fields.damaged_quantity?.value ?? 0} + {doc.evidence.extracted_fields.rejected_quantity?.value ?? 0}) = {doc.validation.unaccounted_quantity}
                  </span>
                  {doc.validation.unaccounted_quantity === 0 ? " ✓" : " ✗"}
                </div>
                
                <div>Signature status: <span className="font-mono">{doc.evidence.extracted_fields.signature_present?.value ? 'Present ✓' : 'Missing ✗'}</span></div>
                
                <div className="mt-2 pt-2 border-t font-bold">
                  Decision: {doc.validation.passed ? "SAFE FOR AUTOMATIC PROCESSING" : "HUMAN REVIEW REQUIRED"}
                </div>
                
                {!doc.validation.passed && (
                  <div className="mt-2">
                    <span className="font-bold text-red-800">Reason:</span>
                    <ul className="list-disc list-inside text-red-700">
                      {doc.validation.failure_reasons.map((r, i) => <li key={i}>{r}</li>)}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          )}

          {doc.decision && (
            <div className="bg-gray-50 p-3 rounded">
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Settlement Decision</h4>
              <div className="text-sm space-y-1">
                <div>Release Amount: ₹{doc.decision.approved_release_amount}</div>
                <div>Reversal Amount: ₹{doc.decision.proposed_reversal_amount}</div>
              </div>
              
              {(() => {
                // Find latest route action in audit logs
                const routeLog = [...(doc.audit_logs || [])].reverse().find(l => l.event_type.startsWith('ROUTE_ACTION'));
                if (routeLog && routeLog.details && routeLog.details.results) {
                  const results = routeLog.details.results;
                  return (
                    <div className="mt-3 border-t pt-2 border-gray-200">
                      <h5 className="text-xs font-semibold text-gray-600 mb-1">Route Execution Results</h5>
                      {results.map((r: any, idx: number) => (
                        <div key={idx} className="bg-white p-2 border rounded mt-1 text-xs">
                          <div className="flex justify-between">
                            <span className="font-bold">{r.action_type}</span>
                            <span className={`px-1 rounded font-bold ${
                              r.status === 'SUCCEEDED' ? 'text-green-700 bg-green-100' : 
                              r.status === 'RECONCILIATION_REQUIRED' ? 'text-yellow-700 bg-yellow-100' : 'text-red-700 bg-red-100'
                            }`}>{r.status}</span>
                          </div>
                          <div className="text-gray-500 mt-1">Amount: ₹{r.amount}</div>
                          <div className="text-gray-500">Mode: <span className="uppercase font-bold text-indigo-600">{r.mode}</span> ({r.provider})</div>
                          {r.error && <div className="text-red-600 mt-1">{r.error}</div>}
                        </div>
                      ))}
                    </div>
                  );
                }
                return null;
              })()}
            </div>
          )}

          {doc.status === 'HUMAN_REVIEW' && (
            <div className="mt-4 border-t pt-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Manual Override</h4>
              <div className="space-y-2 text-sm">
                <div>
                  <label className="block text-xs text-gray-500">Approved Release Amount</label>
                  <input type="number" value={releaseAmt} onChange={e => setReleaseAmt(e.target.value)} className="w-full border rounded p-1" />
                </div>
                <div>
                  <label className="block text-xs text-gray-500">Proposed Reversal Amount</label>
                  <input type="number" value={reversalAmt} onChange={e => setReversalAmt(e.target.value)} className="w-full border rounded p-1" />
                </div>
                <button onClick={submitHumanReview} disabled={loading} className="w-full bg-yellow-500 text-white rounded p-1 hover:bg-yellow-600 disabled:opacity-50">
                  Submit Review
                </button>
              </div>
            </div>
          )}

          {doc.audit_logs && doc.audit_logs.length > 0 && (
            <div className="mt-4 border-t pt-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Append-only Audit Trail</h4>
              <div className="space-y-3">
                {doc.audit_logs.map((log, idx) => (
                  <div key={idx} className="bg-gray-50 p-2 rounded text-xs border border-gray-200 font-mono">
                    <div className="font-bold text-gray-800">{log.event_type}</div>
                    <div className="text-gray-500">{new Date(log.timestamp).toLocaleString()}</div>
                    <div className="mt-1 text-gray-600 overflow-x-auto whitespace-pre-wrap">
                      {JSON.stringify(log.details, null, 2)}
                    </div>
                    <div className="mt-1 text-gray-400 break-all text-[10px]">
                      Hash: {log.event_hash}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
