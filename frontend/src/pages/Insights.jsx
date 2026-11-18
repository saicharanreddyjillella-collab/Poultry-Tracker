import { Link } from 'react-router-dom';
import '../styles/insights.css';

// Admin analysis pages. New insight pages add a card here instead of a menu link.
const INSIGHTS = [
  { to: '/feed-audit', title: 'Feed Audit', tag: 'Protect money',
    text: 'Bag counts vs paper stock and feeding vs the age standard — find where feed is leaving the farm.' },
  { to: '/heat-stress', title: 'Heat Stress', tag: 'Prevent losses',
    text: 'Next 5 days of heat risk per farm from the weather forecast, by bird age and shed type — with what to do.' },
  { to: '/hatcheries', title: 'Chick Quality', tag: 'Prevent losses',
    text: 'First-week mortality, dead on arrival and chick weight by hatchery — evidence for complaints and buying.' },
  { to: '/owner-dashboard', title: 'Owner View', tag: 'Business',
    text: 'Profit, region and grower performance at a glance.' },
  { to: '/break-even', title: 'Break-even', tag: 'Business',
    text: 'Projected cost and break-even rate for live flocks.' },
  { to: '/feed-forecast', title: 'Feed Forecast', tag: 'Planning',
    text: 'Feed needed in the coming weeks, by phase, for production and purchase planning.' },
];

export default function Insights() {
  return (
    <div className="page">
      <h1>Insights</h1>
      <p className="muted">Admin analysis across all farms.</p>
      <div className="insight-cards">
        {INSIGHTS.map(i => (
          <Link key={i.to} to={i.to} className="insight-card">
            <h3>{i.title}</h3>
            <p>{i.text}</p>
            <span className="insight-tag">{i.tag}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
