import { useEffect, useState } from 'react';

export function ToastHost() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    const onToast = (e) => {
      const { msg, type } = e.detail;
      const id = Date.now();
      setItems((prev) => [...prev, { id, msg, type }]);
      setTimeout(() => setItems((prev) => prev.filter((x) => x.id !== id)), 3500);
    };
    window.addEventListener('pc-toast', onToast);
    return () => window.removeEventListener('pc-toast', onToast);
  }, []);

  if (!items.length) return null;
  return (
    <div className="toast-stack">
      {items.map((t) => (
        <div key={t.id} className={`toast toast-${t.type}`}>{t.msg}</div>
      ))}
    </div>
  );
}
