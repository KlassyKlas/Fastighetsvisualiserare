import clsx from 'clsx';
import { ChevronDown } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import {
  PROJECT_STATUSES,
  PROJECT_TYPE_LABELS,
  PROJECT_TYPES,
  STATUS_COLORS,
  STATUS_LABELS,
} from '@/config/map';
import { useUiStore } from '@/store/uiStore';

export default function FilterBar() {
  const filters = useUiStore((s) => s.filters);
  const toggleStatus = useUiStore((s) => s.toggleStatus);
  const toggleProjectType = useUiStore((s) => s.toggleProjectType);

  const [typeDropdownOpen, setTypeDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setTypeDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const activeTypeCount = filters.projectTypes.length;

  return (
    <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-2 bg-slate-800/90 backdrop-blur-sm border border-slate-700 rounded-xl px-4 py-2 shadow-lg">
      {PROJECT_STATUSES.map((status) => {
        const active = filters.statuses.includes(status);
        const color = STATUS_COLORS[status];
        return (
          <button
            key={status}
            onClick={() => toggleStatus(status)}
            className={clsx(
              'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
              active
                ? 'bg-slate-700 text-slate-100'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50',
            )}
          >
            <span
              className="w-2 h-2 rounded-full flex-shrink-0"
              style={{ backgroundColor: color, opacity: active ? 1 : 0.5 }}
            />
            {STATUS_LABELS[status]}
          </button>
        );
      })}

      <div className="w-px h-6 bg-slate-600 mx-1" />

      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => setTypeDropdownOpen(!typeDropdownOpen)}
          className={clsx(
            'flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors',
            activeTypeCount > 0
              ? 'bg-blue-500/20 text-blue-400'
              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-700/50',
          )}
        >
          Projekttyp
          {activeTypeCount > 0 && (
            <span className="bg-blue-500 text-white text-[10px] rounded-full w-4 h-4 flex items-center justify-center">
              {activeTypeCount}
            </span>
          )}
          <ChevronDown
            className={clsx('w-3 h-3 transition-transform', typeDropdownOpen && 'rotate-180')}
          />
        </button>

        {typeDropdownOpen && (
          <div className="absolute top-full mt-2 left-0 bg-slate-800 border border-slate-700 rounded-lg shadow-xl py-1 min-w-[180px] z-20">
            {PROJECT_TYPES.map((projectType) => {
              const active = filters.projectTypes.includes(projectType);
              return (
                <button
                  key={projectType}
                  onClick={() => toggleProjectType(projectType)}
                  className={clsx(
                    'w-full flex items-center gap-3 px-3 py-2 text-xs transition-colors text-left',
                    active
                      ? 'bg-blue-500/10 text-blue-400'
                      : 'text-slate-400 hover:bg-slate-700/50 hover:text-slate-200',
                  )}
                >
                  <span
                    className={clsx(
                      'w-3.5 h-3.5 rounded border flex items-center justify-center flex-shrink-0',
                      active ? 'bg-blue-500 border-blue-500' : 'border-slate-600',
                    )}
                  >
                    {active && (
                      <svg
                        className="w-2.5 h-2.5 text-white"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={3}
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </span>
                  {PROJECT_TYPE_LABELS[projectType]}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
