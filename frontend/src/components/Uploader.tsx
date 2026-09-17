import React, { useState, useEffect } from 'react';
import { apiClient } from '../apiClient';
import axios from 'axios';
import { Upload, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { DocumentResponse, TransferRecord } from '../types';

interface Props {
  onUploadComplete: (doc: DocumentResponse) => void;
}

export default function Uploader({ onUploadComplete }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [transferId, setTransferId] = useState('TRF_DEMO_SAFE');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [transferLoading, setTransferLoading] = useState(false);
  const [transferError, setTransferError] = useState<string | null>(null);
  const [transferRecord, setTransferRecord] = useState<TransferRecord | null>(null);

  useEffect(() => {
    if (!transferId.trim()) {
      setTransferRecord(null);
      setTransferError(null);
      return;
    }

    const controller = new AbortController();
    setTransferLoading(true);
    setTransferError(null);

    apiClient.get<TransferRecord>(`/api/documents/transfers/${transferId.trim()}`, {
      signal: controller.signal,
    })
      .then(res => {
        setTransferRecord(res.data);
        setTransferError(null);
      })
      .catch(err => {
        if (axios.isCancel(err)) return;
        setTransferRecord(null);
        if (err.response?.status === 404) {
          setTransferError("Transfer not found.");
        } else if (err.response?.status === 401) {
          setTransferError("Unauthorized. Check DEMO_ACCESS_TOKEN.");
        } else {
          setTransferError("Failed to fetch transfer.");
        }
      })
      .finally(() => {
        setTransferLoading(false);
      });

    return () => controller.abort();
  }, [transferId]);

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !transferId) return;

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('transfer_id', transferId.trim());

    try {
      const res = await apiClient.post<DocumentResponse>('/api/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onUploadComplete(res.data);
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-bg-surface border border-border-default rounded-md shadow-sm p-6 w-full font-mono">
      <div className="flex items-center mb-6">
        <Upload className="w-5 h-5 text-accent mr-3" />
        <h2 className="text-lg font-bold text-text-primary tracking-tight uppercase">Upload Challan</h2>
      </div>

      <form onSubmit={handleUpload} className="space-y-6">
        
        <div className="space-y-2">
          <label className="block text-xs font-semibold text-text-secondary uppercase tracking-widest">
            Transfer ID Binding
          </label>
          <div className="relative">
            <input
              type="text"
              value={transferId}
              onChange={(e) => setTransferId(e.target.value)}
              className="w-full bg-bg-base border border-border-default rounded p-2.5 text-sm text-text-primary focus:outline-none focus:border-accent font-mono"
              placeholder="e.g. TRF_DEMO_SAFE"
              required
            />
          </div>
          
          <div className="min-h-[60px] p-3 rounded bg-bg-base border border-border-default text-xs">
            {transferLoading && (
              <div className="flex items-center text-text-secondary">
                <Loader2 className="w-3 h-3 animate-spin mr-2" /> Validating transfer...
              </div>
            )}
            {!transferLoading && transferError && (
              <div className="flex items-center text-status-failed">
                <AlertCircle className="w-3 h-3 mr-2" /> {transferError}
              </div>
            )}
            {!transferLoading && transferRecord && (
              <div className="space-y-1 text-text-secondary">
                <div className="flex items-center text-status-safe font-semibold mb-2">
                  <CheckCircle2 className="w-3 h-3 mr-2" /> Valid Transfer Found
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>Vendor: <span className="text-text-primary font-bold">{transferRecord.vendor_name}</span></div>
                  <div>Item: <span className="text-text-primary font-bold">{transferRecord.item_description}</span></div>
                  <div>Quantity: <span className="text-text-primary font-bold">{transferRecord.ordered_quantity} units</span></div>
                  <div>Amount: <span className="text-text-primary font-bold">₹{transferRecord.total_amount}</span></div>
                </div>
              </div>
            )}
            {!transferLoading && !transferError && !transferRecord && transferId.trim() && (
              <div className="text-text-secondary italic">Waiting for input...</div>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <label className="block text-xs font-semibold text-text-secondary uppercase tracking-widest">
            Evidence Image
          </label>
          <input
            type="file"
            accept="image/*"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="w-full text-sm text-text-secondary file:mr-4 file:py-2 file:px-4 file:rounded file:border-0 file:bg-bg-elevated file:text-text-primary file:font-semibold hover:file:bg-border-default file:cursor-pointer cursor-pointer border border-border-default rounded p-2 bg-bg-base"
            required
          />
        </div>

        {error && (
          <div className="p-3 bg-status-failed/10 border border-status-failed/30 rounded text-status-failed text-xs flex items-start">
            <AlertCircle className="w-4 h-4 mr-2 mt-0.5 flex-shrink-0" />
            <div>
              <div className="font-bold uppercase tracking-wider mb-1">UPLOAD REJECTED</div>
              <div>{error}</div>
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !file || !transferRecord}
          className="w-full flex items-center justify-center p-3 rounded font-bold text-sm bg-accent text-white hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors tracking-wider uppercase"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
              Uploading...
            </>
          ) : (
            'Process Evidence'
          )}
        </button>
      </form>
    </div>
  );
}
