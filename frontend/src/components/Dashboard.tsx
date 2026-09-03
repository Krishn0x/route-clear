import { useState } from 'react';
import Uploader from './Uploader';
import DocumentViewer from './DocumentViewer';
import SafetyPanel from './SafetyPanel';
import { DocumentResponse } from '../types';

export default function Dashboard() {
  const [doc, setDoc] = useState<DocumentResponse | null>(null);

  return (
    <div className="space-y-6">
      {!doc ? (
        <div className="max-w-xl mx-auto">
          <Uploader onUploadComplete={setDoc} />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[800px]">
          <DocumentViewer doc={doc} />
          <SafetyPanel doc={doc} onUpdate={setDoc} />
        </div>
      )}
    </div>
  );
}
