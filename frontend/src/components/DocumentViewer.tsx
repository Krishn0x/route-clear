import { useRef } from 'react';
import { DocumentResponse } from '../types';

interface Props {
  doc: DocumentResponse;
}

export default function DocumentViewer({ doc }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // Still using the API image fetcher since we just have the ID
  const imageUrl = `/api/documents/${doc.id}/image`;

  return (
    <div className="bg-bg-surface border border-border-default rounded-md p-4 h-full relative flex flex-col" ref={containerRef}>
      <h3 className="text-sm font-bold text-text-primary mb-3 uppercase tracking-widest font-mono flex items-center justify-between">
        <span>Original Document</span>
        <span className="text-text-secondary text-[10px]">{doc.id}</span>
      </h3>
      <div className="relative border border-border-default bg-bg-base rounded overflow-hidden flex-1 flex items-center justify-center p-2">
        <img 
          ref={imgRef}
          src={imageUrl} 
          alt="Document Evidence" 
          className="max-w-full max-h-full object-contain"
        />
      </div>
    </div>
  );
}
