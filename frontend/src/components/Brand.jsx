import Icon from "./Icon";
export default function Brand() {
  return (
    <span className="brand">
      <span className="brand-mark">
        <Icon name="shield" size={23} />
      </span>
      <span className="brand-name">
        Samadhan Setu
        <span className="brand-subtitle">A better way forward</span>
      </span>
    </span>
  );
}
