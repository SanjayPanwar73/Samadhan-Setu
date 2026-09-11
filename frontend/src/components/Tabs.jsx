export default function Tabs({ tabs, value, onChange }) {
  function handleKey(event) {
    const index = tabs.findIndex((tab) => tab.id === value);
    const next =
      event.key === "ArrowRight"
        ? (index + 1) % tabs.length
        : event.key === "ArrowLeft"
          ? (index - 1 + tabs.length) % tabs.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? tabs.length - 1
              : null;
    if (next === null) return;
    event.preventDefault();
    onChange(tabs[next].id);
    document.getElementById(`tab-${tabs[next].id}`)?.focus();
  }
  return (
    <div
      className="tabs"
      role="tablist"
      aria-label="Workspace sections"
      onKeyDown={handleKey}
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          id={`tab-${tab.id}`}
          role="tab"
          aria-selected={value === tab.id}
          aria-controls={`panel-${tab.id}`}
          tabIndex={value === tab.id ? 0 : -1}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
