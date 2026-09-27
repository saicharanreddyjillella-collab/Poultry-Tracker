import { Link } from 'react-router-dom';

export default function Landing() {
  return (
    <div className="landing">
      <div className="landing-head">
        <h1>Sai Ram Group</h1>
        <p>Choose a business to manage</p>
      </div>
      <div className="landing-cards">
        <Link to="/feeds" className="landing-card landing-card-feeds">
          <span className="landing-emoji">🐔</span>
          <h2>Sai Ram Feeds</h2>
          <p>Broiler integration — farms, flocks, feed &amp; farmer billing</p>
          <span className="landing-go">Open →</span>
        </Link>
        <Link to="/chicken" className="landing-card landing-card-chicken">
          <span className="landing-emoji">🛒</span>
          <h2>Sai Charan Chicken Center</h2>
          <p>Live-bird trading — sales, purchases, collections &amp; accounts</p>
          <span className="landing-go">Open →</span>
        </Link>
      </div>
    </div>
  );
}
