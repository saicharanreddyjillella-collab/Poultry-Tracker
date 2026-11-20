import useFeedTypes from '../utils/useFeedTypes';

/** A feed type shown by its current code, in the colour the admin chose. */
export default function FeedBadge({ type, children, className = '' }) {
  const { code, colour } = useFeedTypes();
  const c = colour(type);
  return (
    <span className={`feed-badge ${className}`} style={{ color: c, background: `${c}1A`, borderColor: `${c}40` }}>
      {children ?? code(type)}
    </span>
  );
}
