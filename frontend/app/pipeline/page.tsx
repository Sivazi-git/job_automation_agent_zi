import PipelinePanel from '@/components/PipelinePanel';

export default function PipelinePage() {
  return (
    <div className="p-6 max-w-2xl">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-100">Pipeline Control</h1>
        <p className="text-sm text-slate-400 mt-0.5">
          Trigger and monitor the job automation pipeline
        </p>
      </div>
      <PipelinePanel />
    </div>
  );
}
