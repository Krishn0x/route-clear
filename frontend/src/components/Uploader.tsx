import React, { useState } from 'react';
import axios from 'axios';
import { Upload, Loader2 } from 'lucide-react';
import { DocumentResponse } from '../types';

interface Props {
  onUploadComplete: (doc: DocumentResponse) => void;
}

export default function Uploader({ onUploadComplete }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const [transferId, setTransferId] = useState(`tr_demo_${Date.now()}`);
  const [totalAmount, setTotalAmount] = useState('100000.00');
  const [orderedQuantity, setOrderedQuantity] = useState('100');

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    if (parseFloat(totalAmount) <= 0) {
      setError("Total amount must be greater than 0");
      return;
    }
    if (parseInt(orderedQuantity, 10) <= 0) {
      setError("Ordered quantity must be a positive integer");
      return;
    }

    setLoading(true);
    setError(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('transfer_id', transferId);
    formData.append('total_amount', totalAmount);
    formData.append('ordered_quantity', orderedQuantity);

    try {
      const res = await axios.post<DocumentResponse>('/api/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      onUploadComplete(res.data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700">Transfer ID</label>
          <input 
            type="text" 
            value={transferId} 
            onChange={e => setTransferId(e.target.value)} 
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border" 
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Total Amount (₹)</label>
          <input 
            type="number" 
            step="0.01"
            value={totalAmount} 
            onChange={e => setTotalAmount(e.target.value)} 
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border" 
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700">Ordered Quantity</label>
          <input 
            type="number" 
            value={orderedQuantity} 
            onChange={e => setOrderedQuantity(e.target.value)} 
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 sm:text-sm px-3 py-2 border" 
          />
        </div>
      </div>
      
      <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:bg-gray-50 transition">
        {loading ? (
          <div className="flex flex-col items-center">
            <Loader2 className="h-10 w-10 text-indigo-500 animate-spin mb-4" />
            <p className="text-gray-600">Uploading and analyzing document...</p>
          </div>
        ) : (
          <div>
            <Upload className="mx-auto h-12 w-12 text-gray-400" />
            <div className="mt-4 flex text-sm text-gray-600 justify-center">
              <label htmlFor="file-upload" className="relative cursor-pointer bg-white rounded-md font-medium text-indigo-600 hover:text-indigo-500 focus-within:outline-none focus-within:ring-2 focus-within:ring-offset-2 focus-within:ring-indigo-500">
                <span>Upload a delivery challan</span>
                <input id="file-upload" name="file-upload" type="file" className="sr-only" onChange={handleUpload} accept="image/*" />
              </label>
            </div>
            <p className="text-xs text-gray-500 mt-2">JPEG, PNG up to 10MB</p>
          </div>
        )}
        {error && <p className="mt-4 text-red-600 text-sm">{error}</p>}
      </div>
    </div>
  );
}
