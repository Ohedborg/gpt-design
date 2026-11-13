// Demo component for scanner verification; not a bundled live preview.
export function Button({ children }: { children: React.ReactNode }) {
  return <button style={{ background: 'var(--color-accent)', padding: 16 }}>{children}</button>;
}
