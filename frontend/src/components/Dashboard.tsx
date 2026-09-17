import { useState } from 'react';
import Uploader from './Uploader';
import DocumentViewer from './DocumentViewer';
import SafetyPanel from './SafetyPanel';
import { DocumentResponse } from '../types';
import { Shield, BrainCircuit, Scale, Lock, ArrowRight, FileSearch, UserCheck } from 'lucide-react';

function ArchitectureDiagram() {
  return (
    <div className="w-full max-w-4xl mx-auto mt-12 mb-8 bg-bg-surface border border-border-default rounded-md p-6 shadow-sm">
      <div className="text-center mb-8">
        <h2 className="text-xl font-bold tracking-tight mb-2">Architecture Integrity</h2>
        <p className="text-accent font-mono text-sm">"AI interprets evidence. Deterministic code decides money."</p>
      </div>
      
      <div className="flex flex-col md:flex-row items-center justify-between space-y-4 md:space-y-0 text-xs">
        
        {/* Evidence */}
        <div className="flex flex-col items-center flex-1">
          <div className="h-10 w-10 rounded bg-bg-elevated border border-border-default flex items-center justify-center mb-2">
            <FileSearch className="w-5 h-5 text-text-secondary" />
          </div>
          <span className="font-mono text-center">EVIDENCE</span>
        </div>
        
        <ArrowRight className="w-4 h-4 text-border-default hidden md:block" />
        
        {/* AI Pass 1 */}
        <div className="flex flex-col items-center flex-1">
          <div className="h-10 w-10 rounded bg-bg-elevated border border-accent/30 flex items-center justify-center mb-2">
            <BrainCircuit className="w-5 h-5 text-accent" />
          </div>
          <span className="font-mono text-center">AI PASS 1</span>
        </div>

        <ArrowRight className="w-4 h-4 text-border-default hidden md:block" />

        {/* AI Pass 2 */}
        <div className="flex flex-col items-center flex-1">
          <div className="h-10 w-10 rounded bg-bg-elevated border border-accent/30 flex items-center justify-center mb-2">
            <BrainCircuit className="w-5 h-5 text-accent" />
          </div>
          <span className="font-mono text-center">AI PASS 2<br/><span className="text-[9px] text-text-secondary">(INDEPENDENT)</span></span>
        </div>

        <ArrowRight className="w-4 h-4 text-border-default hidden md:block" />

        {/* Deterministic */}
        <div className="flex flex-col items-center flex-1">
          <div className="h-10 w-10 rounded bg-bg-elevated border border-status-safe/30 flex items-center justify-center mb-2">
            <Scale className="w-5 h-5 text-status-safe" />
          </div>
          <span className="font-mono text-center">COMPARATOR<br/><span className="text-[9px] text-text-secondary">DETERMINISTIC</span></span>
        </div>

        <ArrowRight className="w-4 h-4 text-border-default hidden md:block" />

        {/* Groundedness */}
        <div className="flex flex-col items-center flex-1">
          <div className="h-10 w-10 rounded bg-bg-elevated border border-status-safe/30 flex items-center justify-center mb-2">
            <Shield className="w-5 h-5 text-status-safe" />
          </div>
          <span className="font-mono text-center">GROUNDEDNESS<br/><span className="text-[9px] text-text-secondary">DETERMINISTIC</span></span>
        </div>

        <ArrowRight className="w-4 h-4 text-border-default hidden md:block" />

        {/* Safety Engine */}
        <div className="flex flex-col items-center flex-1">
          <div className="h-10 w-10 rounded bg-bg-elevated border border-status-safe/30 flex items-center justify-center mb-2">
            <Lock className="w-5 h-5 text-status-safe" />
          </div>
          <span className="font-mono text-center">SAFETY ENGINE<br/><span className="text-[9px] text-text-secondary">DETERMINISTIC</span></span>
        </div>

        <ArrowRight className="w-4 h-4 text-border-default hidden md:block" />

        {/* Final */}
        <div className="flex flex-col items-center flex-1">
          <div className="h-10 w-10 rounded bg-bg-elevated border border-status-review/30 flex items-center justify-center mb-2">
            <UserCheck className="w-5 h-5 text-status-review" />
          </div>
          <span className="font-mono text-center">HUMAN REVIEW<br/><span className="text-[9px] text-text-secondary">OR ROUTE ACTION</span></span>
        </div>
      </div>
      
      <div className="mt-8 pt-6 border-t border-border-default text-xs text-text-secondary text-center space-y-2">
        <p><strong className="text-text-primary">System Limitation:</strong> A perfectly consistent VLM hallucination across both passes cannot be proven physically correct by software alone.</p>
        <p>In all cases of AI disagreement, ungrounded evidence, or negative validation, execution safely delegates to human review.</p>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [doc, setDoc] = useState<DocumentResponse | null>(null);

  return (
    <div className="w-full flex-1 flex flex-col space-y-6">
      {!doc ? (
        <div className="w-full mx-auto flex flex-col items-center justify-center flex-1">
          <ArchitectureDiagram />
          <div className="w-full max-w-xl">
            <Uploader onUploadComplete={setDoc} />
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-[800px]">
          <DocumentViewer doc={doc} />
          <SafetyPanel doc={doc} onUpdate={setDoc} />
        </div>
      )}
    </div>
  );
}
