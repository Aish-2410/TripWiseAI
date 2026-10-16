import { Link } from "react-router-dom";
import { EmptyState } from "../components/ui";
export default function NotFound() {
  return <div className="px-5 py-24"><EmptyState title="This path is off the map" action={<Link to="/" className="btn-gold">Back to the start</Link>}>The page you were looking for does not exist.</EmptyState></div>;
}
