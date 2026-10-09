import type { ReactNode } from 'react';

type FeedbackVariant = 'success' | 'warning' | 'info';

export function StatusIcon({ variant }: { variant: FeedbackVariant }) {
  return <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {variant === 'info' ? <><path d="M20 7v5h-5"/><path d="M4 17v-5h5"/><path d="M6.2 7a7 7 0 0 1 11.6-1L20 9M4 15l2.2 3A7 7 0 0 0 17.8 17"/></> : <>
      <path d="M12 3 20 6v5c0 5-3.8 8.2-8 10-4.2-1.8-8-5-8-10V6l8-3Z"/>
      {variant === 'success' ? <path d="m8.5 11.5 2.5 2.5 4.5-4.5"/> : <><path d="M12 8v5"/><circle cx="12" cy="16.5" r=".8" fill="currentColor" stroke="none"/></>}
    </>}
  </svg>;
}

export function FeedbackNotice({ variant, children, className = '', role }: { variant: FeedbackVariant; children: ReactNode; className?: string; role?: 'alert' | 'status' }) {
  return <div className={`feedback feedback--${variant} ${className}`} role={role}>
    <span className="feedback-icon"><StatusIcon variant={variant}/></span>
    <span className="feedback-message">{children}</span>
  </div>;
}
