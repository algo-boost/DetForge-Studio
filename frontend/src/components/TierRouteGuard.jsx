import { useEffect } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { resolveDefaultHome } from '../config/personas';
import { fallbackPathForTier, isPathAllowedForTier } from '../config/nav';
import { useUserPrefs } from '../context/UserPrefsContext';

export default function TierRouteGuard() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { tier, persona, defaultHome } = useUserPrefs();

  useEffect(() => {
    if (isPathAllowedForTier(pathname, tier)) return;
    const home = fallbackPathForTier(
      tier,
      defaultHome || resolveDefaultHome(persona, tier),
    );
    navigate(home, { replace: true });
  }, [pathname, tier, persona, defaultHome, navigate]);

  return <Outlet />;
}
