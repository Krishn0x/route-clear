import { useRef } from 'react';
import { DocumentResponse } from '../types';

interface Props {
  doc: DocumentResponse;
}

export default function DocumentViewer({ doc }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  // We don't have an endpoint to serve the raw image in FastAPI right now easily, 
  // but wait! The API doesn't have a GET /documents/{id}/image endpoint.
  // We need to add one, or use a dummy image for now.
  // Actually, I can just write the backend route for it quickly.
  const imageUrl = `/api/documents/${doc.id}/image`;

  const drawBoxes = () => {
    // We would draw boxes here over the image based on evidence_region
  };

  return (
    <div className="bg-white shadow rounded-lg p-4 h-full relative" ref={containerRef}>
      <h3 className="text-lg font-medium text-gray-900 mb-4">Original Document</h3>
      <div className="relative border bg-gray-100 rounded overflow-hidden" style={{ minHeight: '400px' }}>
        <img 
          ref={imgRef}
          src={imageUrl} 
          alt="Document" 
          className="w-full h-auto object-contain"
          onLoad={drawBoxes}
        />
        {/* Draw bounding boxes here */}
      </div>
    </div>
  );
}
