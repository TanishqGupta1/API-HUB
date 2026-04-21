"use client";

import React from "react";
import { Button } from "./button";

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: React.ReactNode;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export function EmptyState({ title, description, icon, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center border-2 border-dashed rounded-xl bg-vellum/30" style={{ borderColor: 'var(--border)', minHeight: '320px' }}>
      <div className="flex items-center justify-center w-16 h-16 mb-6 rounded-full bg-paper" style={{ border: '1px solid var(--border)', color: 'var(--ink-muted)' }}>
        {icon || (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        )}
      </div>
      <h3 className="mb-2 text-lg font-semibold" style={{ color: 'var(--ink)' }}>{title}</h3>
      <p className="max-w-xs mb-8 text-sm leading-relaxed" style={{ color: 'var(--ink-muted)' }}>
        {description}
      </p>
      {action && (
        <Button onClick={action.onClick} className="px-6 py-2 shadow-sm">
          {action.label}
        </Button>
      )}
    </div>
  );
}
