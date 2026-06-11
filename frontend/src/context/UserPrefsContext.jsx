import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import {
  normalizePersona,
  personasForTier,
  resolveDefaultHome,
} from '../config/personas';
import { USER_TIERS } from '../config/nav';

const TIER_KEY = 'iisp.user.tier';
const PERSONA_KEY = 'iisp.user.persona';
const DEFAULT_HOME_KEY = 'iisp.user.defaultHome';

const UserPrefsContext = createContext({
  tier: USER_TIERS.CONFIGURER,
  persona: 'sa',
  defaultHome: '/',
  setTier: () => {},
  setPersona: () => {},
  setDefaultHome: () => {},
  resetDefaultHome: () => {},
});

function readTier() {
  try {
    const v = localStorage.getItem(TIER_KEY);
    if (v === USER_TIERS.OPERATOR || v === USER_TIERS.CONFIGURER) return v;
  } catch {
    /* ignore */
  }
  return USER_TIERS.CONFIGURER;
}

function readPersona(tier) {
  try {
    const v = localStorage.getItem(PERSONA_KEY);
    if (v) return normalizePersona(v, tier);
  } catch {
    /* ignore */
  }
  return normalizePersona(null, tier);
}

function readDefaultHomeOverride() {
  try {
    const v = localStorage.getItem(DEFAULT_HOME_KEY);
    if (v && v.startsWith('/')) return v;
  } catch {
    /* ignore */
  }
  return null;
}

export function UserPrefsProvider({ children }) {
  const [tier, setTierState] = useState(readTier);
  const [persona, setPersonaState] = useState(() => readPersona(readTier()));
  const [defaultHomeOverride, setDefaultHomeOverride] = useState(readDefaultHomeOverride);

  const defaultHome = useMemo(
    () => defaultHomeOverride || resolveDefaultHome(persona, tier),
    [defaultHomeOverride, persona, tier],
  );

  const setTier = useCallback((next) => {
    const value = next === USER_TIERS.OPERATOR ? USER_TIERS.OPERATOR : USER_TIERS.CONFIGURER;
    const normalizedPersona = normalizePersona(persona, value);
    setTierState(value);
    setPersonaState(normalizedPersona);
    try {
      localStorage.setItem(TIER_KEY, value);
      localStorage.setItem(PERSONA_KEY, normalizedPersona);
    } catch {
      /* ignore */
    }
  }, [persona]);

  const setPersona = useCallback((next) => {
    setPersonaState((prev) => {
      const normalized = normalizePersona(next, tier);
      try {
        localStorage.setItem(PERSONA_KEY, normalized);
      } catch {
        /* ignore */
      }
      return normalized;
    });
  }, [tier]);

  const setDefaultHome = useCallback((path) => {
    const value = path && path.startsWith('/') ? path : null;
    setDefaultHomeOverride(value);
    try {
      if (value) localStorage.setItem(DEFAULT_HOME_KEY, value);
      else localStorage.removeItem(DEFAULT_HOME_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const resetDefaultHome = useCallback(() => {
    setDefaultHome(null);
  }, [setDefaultHome]);

  const value = useMemo(
    () => ({
      tier,
      persona,
      defaultHome,
      defaultHomeOverride,
      personaOptions: personasForTier(tier),
      setTier,
      setPersona,
      setDefaultHome,
      resetDefaultHome,
    }),
    [tier, persona, defaultHome, defaultHomeOverride, setTier, setPersona, setDefaultHome, resetDefaultHome],
  );

  return (
    <UserPrefsContext.Provider value={value}>
      {children}
    </UserPrefsContext.Provider>
  );
}

export function useUserPrefs() {
  return useContext(UserPrefsContext);
}
