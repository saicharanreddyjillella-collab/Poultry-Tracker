import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/** Shown in place of a page whose feature the admin has switched off. */
export default function FeatureOff({ name }) {
  const { isAdmin } = useAuth();
  return (
    <div className="page">
      <h1>{name}</h1>
      <div className="alert-banner alert-banner-warning" role="status">
        {name} is turned off.{' '}
        {isAdmin ? <>Turn it on in <Link to="/settings">Settings → Features</Link>.</> : 'Ask the admin to turn it on.'}
      </div>
    </div>
  );
}
