import Modal from "./Modal";

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive = false,
  onConfirm,
  onCancel,
  busy = false,
}) {
  return (
    <Modal open={open} onClose={onCancel}>
      <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
      {message && <p className="mt-2 text-sm text-gray-600">{message}</p>}
      <div className="mt-6 flex justify-end gap-3">
        <button
          onClick={onCancel}
          disabled={busy}
          className="text-sm font-medium px-4 py-2 rounded-lg text-gray-700
                     hover:bg-gray-100 transition disabled:opacity-50"
        >
          {cancelLabel}
        </button>
        <button
          onClick={onConfirm}
          disabled={busy}
          className={`text-sm font-medium px-4 py-2 rounded-lg text-white
                      transition disabled:opacity-50 ${
                        destructive
                          ? "bg-red-600 hover:bg-red-700"
                          : "bg-indigo-600 hover:bg-indigo-700"
                      }`}
        >
          {busy ? "Working…" : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}
