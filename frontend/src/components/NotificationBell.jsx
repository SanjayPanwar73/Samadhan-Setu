import { Link } from "react-router-dom";
import Icon from "./Icon";
import useUnreadCount from "../hooks/useUnreadCount";

export default function NotificationBell() {
  const { count } = useUnreadCount();
  return (
    <Link to="/notifications" className="icon-button relative" aria-label={count ? `Notifications, ${count} unread` : "Notifications"}>
      <Icon name="bell" size={18} />
      {count > 0 && (
        <span className="absolute -right-1 -top-1 min-w-4 rounded-full bg-red-600 px-1 text-center text-[10px] font-semibold leading-4 text-white" aria-hidden="true">
          {count > 99 ? "99+" : count}
        </span>
      )}
    </Link>
  );
}
