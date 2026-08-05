import clsx from 'clsx';

export default function Toggle({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <button
      onClick={onChange}
      className={clsx(
        'relative w-10 h-5 rounded-full transition-colors flex-shrink-0',
        checked ? 'bg-blue-500' : 'bg-slate-600',
      )}
    >
      <div
        className={clsx(
          'absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform shadow-sm',
          checked ? 'translate-x-5' : 'translate-x-0.5',
        )}
      />
    </button>
  );
}
