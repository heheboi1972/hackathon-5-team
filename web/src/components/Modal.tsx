import { useEffect, useId } from "react";
import type { HTMLAttributes, ReactNode } from "react";

export interface ModalProps extends Omit<HTMLAttributes<HTMLDivElement>, "title"> {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  children: ReactNode;
}

export default function Modal({
  open,
  onClose,
  title,
  children,
  className,
  ...props
}: ModalProps) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;

    const previousOverflow = document.body.style.overflow;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };

    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", onKeyDown);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [onClose, open]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        {...props}
        aria-labelledby={title ? titleId : undefined}
        aria-modal="true"
        className={["w-full max-w-lg rounded-lg bg-white p-6 shadow-xl", className]
          .filter(Boolean)
          .join(" ")}
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4">
          {title ? (
            <h2 id={titleId} className="text-lg font-semibold text-gray-900">
              {title}
            </h2>
          ) : (
            <span />
          )}
          <button
            type="button"
            aria-label="닫기"
            className="rounded p-1 text-xl leading-none text-gray-500 hover:bg-gray-100 hover:text-gray-700"
            onClick={onClose}
          >
            ×
          </button>
        </div>
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}
