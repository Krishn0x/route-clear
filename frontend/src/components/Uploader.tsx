import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Upload, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react';
import { DocumentResponse, TransferRecord } from '../types';

interface Props {
  onUploadComplete: (doc: DocumentResponse) => void;
}

const DEMO_TRANSFER_IDS = [
  { id: 'TRF_DEMO_SAFE',     label: 'SAFE demo  (challan_043)' },
  { id: 'TRF_DEMO_REVIEW',   label: 'UNACCOUNTED demo  (challan_053)' },
  { id: 'TRF_DEMO_CONFLICT', label: 'CONFLICT demo  (simulated)' },
];

export default function Uploader({ onUploadComplete }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [transferId, setTransferId] = useState('TRF_DEMO_SAFE');
  const [transfer, setTransfer] = useState<TransferRecord | null>(null);
  const [transferError, setTransferError] = useState<string | null>(null);
  const [transferLoading, setTransferLoading] = useState(false);

  // Look up transfer metadata whenever the transfer ID changes
  useEffect(() => {
    if (!transferId.trim()) {
      setTransfer(null);
      return;
    }
    const controller = new AbortController();
    setTransferLoading(true);
    setTransferError(null);

    axios.get<TransferRecord>(`/api/documents/transfers/${transferId.trim()}`, {
      signal: controller.signal,
    })
      .then(res => {
        setTransfer(res.data);
        setTransferError(null);
      })
      .catch(err => {
        if (axios.isCancel(err)) return;
        setTransfer(null);
        setTransferError(err.response?.data?.detail || 'Transfer not found');
      })
      .finally(() => setTransferLoading(false));

    return () => controller.abort();
  }, [transferId]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!transfer) {
      setError('Please enter a valid Transfer ID before uploading.');
      return;
    }

    setLoading(true);
    setError(null);

    // V2: only transfer_id and file are sent — financial fields come from the
    // server-side transfer registry, never from user input.
    const formData = new FormData();
    formData.append('file', file);
    formData.append('transfer_id', transferId.trim());

    try {
      const res = await axios.post<DocumentResponse>('/api/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      onUploadComplete(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
      // Reset the file input so the same file can be re-uploaded after a DB reset
      e.target.value = '';
    }
  };

  return (
    <div className="bg-white shadow rounded-lg p-6">

      {/* Transfer ID selector */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Transfer ID
          <span className="ml-2 text-xs text-gray-400 font-normal">
            (ordered quantity and amount are loaded from server records)
          </span>
        </label>

        {/* Quick demo selector */}
        <div className="flex flex-wrap gap-2 mb-2">
          {DEMO_TRANSFER_IDS.map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setTransferId(id)}
              className={`text-xs px-3 py-1 rounded-full border transition ${
                transferId === id
                  ? 'bg-indigo-600 text-white border-indigo-600'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-indigo-400'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <input
          type="text"
          value={transferId}
          onChange={e => setTransferId(e.target.value)}
          placeholder="TRF_DEMO_SAFE"
          className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border"
        />
      </div>

      {/* Transfer metadata preview */}
      {transferLoading && (
        <div className="mb-4 flex items-center text-sm text-gray-500">
          <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Looking up transfer…
        </div>
      )}

      {transferError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded flex items-start text-sm text-red-700">
          <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0 mt-0.5" />
          {transferError}
        </div>
      )}

      {transfer && !transferLoading && (
        <div className="mb-6 p-3 bg-green-50 border border-green-200 rounded text-sm">
          <div className="flex items-center mb-2 text-green-800 font-medium">
            <CheckCircle2 className="w-4 h-4 mr-2" /> Transfer found — metadata loaded from server
          </div>
          <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-gray-700">
            <div><span className="text-gray-500">Vendor:</span> {transfer.vendor_name}</div>
            <div><span className="text-gray-500">Item:</span> {transfer.item_description}</div>
            <div><span className="text-gray-500">Ordered qty:</span> <span className="font-mono font-semibold">{transfer.ordered_quantity}</span></div>
            <div><span className="text-gray-500">Total amount:</span> <span className="font-mono font-semibold">₹{Number(transfer.total_amount).toLocaleString('en-IN')}</span></div>
          </div>
        </div>
      )}

      {/* Upload area */}
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:bg-gray-50 transition">
        {loading ? (
          <div className="flex flex-col items-center">
            <Loader2 className="h-10 w-10 text-indigo-500 animate-spin mb-4" />
            <p className="text-gray-600">Uploading document…</p>
          </div>
        ) : (
          <div>
            <Upload className="mx-auto h-12 w-12 text-gray-400" />
            <div className="mt-4 flex text-sm text-gray-600 justify-center">
              <label
                htmlFor="file-upload"
                className={`relative cursor-pointer bg-white rounded-md font-medium ${
                  transfer
                    ? 'text-indigo-600 hover:text-indigo-500'
                    : 'text-gray-400 cursor-not-allowed'
                } focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500`}
              >
                <span>Upload a delivery challan</span>
                <input
                  id="file-upload"
                  name="file-upload"
                  type="file"
                  className="sr-only"
                  onChange={handleUpload}
                  accept="image/*"
                  disabled={!transfer}
                />
              </label>
            </div>
            <p className="text-xs text-gray-500 mt-2">JPEG, PNG up to 5 MB</p>
            {!transfer && !transferLoading && (
              <p className="text-xs text-orange-500 mt-1">Select a valid Transfer ID above to enable upload.</p>
            )}
          </div>
        )}
        {error && (
          <p className="mt-4 text-red-600 text-sm flex items-center justify-center">
            <AlertCircle className="w-4 h-4 mr-1" /> {error}
          </p>
        )}
      </div>
    </div>
  );
}
