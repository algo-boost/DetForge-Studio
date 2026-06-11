/**
 * L1/L2 岗位 persona 与默认首页（U5）
 * @see docs/PRODUCT_DESIGN.md §2
 */

import { USER_TIERS } from './nav';

export const PERSONAS = {
  delivery: {
    id: 'delivery',
    label: '交付',
    tier: USER_TIERS.OPERATOR,
    defaultHome: '/',
  },
  customer_qc: {
    id: 'customer_qc',
    label: '客户质检',
    tier: USER_TIERS.OPERATOR,
    defaultHome: '/',
  },
  sa: {
    id: 'sa',
    label: '解决方案',
    tier: USER_TIERS.CONFIGURER,
    defaultHome: '/flows',
  },
  algo: {
    id: 'algo',
    label: '算法',
    tier: USER_TIERS.CONFIGURER,
    defaultHome: '/query',
  },
  optical: {
    id: 'optical',
    label: '光学',
    tier: USER_TIERS.CONFIGURER,
    defaultHome: '/',
  },
};

/** @typedef {keyof typeof PERSONAS} PersonaId */

export const PERSONA_LIST = Object.values(PERSONAS);

/**
 * @param {PersonaId | string} personaId
 * @returns {typeof PERSONAS[PersonaId] | null}
 */
export function getPersona(personaId) {
  return PERSONAS[personaId] || null;
}

/**
 * @param {import('./nav').UserTier} tier
 * @returns {typeof PERSONAS[PersonaId][]}
 */
export function personasForTier(tier) {
  const t = tier === USER_TIERS.OPERATOR ? USER_TIERS.OPERATOR : USER_TIERS.CONFIGURER;
  return PERSONA_LIST.filter((p) => p.tier === t);
}

/**
 * @param {PersonaId | string} personaId
 * @param {import('./nav').UserTier} tier
 */
export function resolveDefaultHome(personaId, tier) {
  const persona = getPersona(personaId);
  if (persona && persona.tier === tier) return persona.defaultHome;
  const fallback = personasForTier(tier)[0];
  return fallback?.defaultHome || '/';
}

/**
 * @param {PersonaId | string | null | undefined} personaId
 * @param {import('./nav').UserTier} tier
 * @returns {PersonaId}
 */
export function normalizePersona(personaId, tier) {
  const persona = getPersona(personaId);
  if (persona && persona.tier === tier) return persona.id;
  return personasForTier(tier)[0]?.id || 'delivery';
}
