import { Link } from 'react-router-dom';
import brand from '../config/brand';

export default function Landing() {
  return (
    <div className="landing">
      <div className="landing-head">
        <h1>{brand.company}</h1>
        <p>Choose a business to manage</p>
      </div>
      <div className="landing-cards">
        <Link to="/feeds" className="landing-card landing-card-feeds">
          <span className="landing-emoji">🐔</span>
          <h2>{brand.feedsName}</h2>
          <p>Broiler integration — farms, flocks, feed &amp; farmer billing</p>
          <span className="landing-go">Open →</span>
        </Link>
        <Link to="/chicken" className="landing-card landing-card-chicken">
          <span className="landing-emoji">🛒</span>
          <h2>{brand.chickenName}</h2>
          <p>Live-bird trading — sales, purchases, collections &amp; accounts</p>
          <span className="landing-go">Open →</span>
        </Link>
        <Link to="/layer" className="landing-card landing-card-layer">
          <span className="landing-emoji">🥚</span>
          <h2>{brand.layerName}</h2>
          <p>Egg production — per-flock cost, feed milling, egg sales &amp; accounts</p>
          <span className="landing-go">Open →</span>
        </Link>
      </div>
    </div>
  );
}
