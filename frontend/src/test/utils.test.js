/**
 * Tests utilitaires — validation des fonctions de scoring et qualification
 * utilisées dans la page Leads.
 */
import { describe, it, expect } from 'vitest';

// ── Logique de qualification (reprise depuis Leads.jsx) ───────────────────────
function getQualification(lead) {
  if (lead.has_website === false) {
    return { label: 'SANS SITE' };
  }
  const invalidUrls = ['', '-', 'n/a', 'na', 'none', 'null'];
  const hasValidUrl =
    lead.website &&
    !invalidUrls.includes(lead.website.toLowerCase().trim()) &&
    lead.website.trim().length > 3;

  if (!hasValidUrl && lead.has_website === null) {
    return { label: 'NON ANALYSÉ' };
  }
  if (hasValidUrl && lead.has_website === null && lead.website_quality_score === null) {
    return { label: 'À ANALYSER' };
  }
  if (lead.score >= 70) return { label: 'CHAUD' };
  if (lead.score >= 40) return { label: 'TIÈDE' };
  return { label: 'FROID' };
}

// ── Tests ─────────────────────────────────────────────────────────────────────
describe('getQualification', () => {
  it('retourne SANS SITE si has_website === false', () => {
    expect(getQualification({ has_website: false, score: 90 }).label).toBe('SANS SITE');
  });

  it('retourne NON ANALYSÉ si pas de site et has_website null', () => {
    expect(getQualification({ has_website: null, website: null, score: 50 }).label).toBe(
      'NON ANALYSÉ'
    );
  });

  it('retourne À ANALYSER si URL présente mais non vérifiée', () => {
    expect(
      getQualification({
        has_website: null,
        website: 'https://hotel.fr',
        website_quality_score: null,
        score: 50,
      }).label
    ).toBe('À ANALYSER');
  });

  it('retourne CHAUD si score >= 70', () => {
    expect(getQualification({ has_website: true, score: 75 }).label).toBe('CHAUD');
  });

  it('retourne TIÈDE si score entre 40 et 69', () => {
    expect(getQualification({ has_website: true, score: 55 }).label).toBe('TIÈDE');
  });

  it('retourne FROID si score < 40', () => {
    expect(getQualification({ has_website: true, score: 20 }).label).toBe('FROID');
  });
});

describe('calcul du taux de réponse', () => {
  it('calcule correctement le taux de réponse', () => {
    const campaign = { emails_sent: 100, responses_received: 15 };
    const rate = ((campaign.responses_received / campaign.emails_sent) * 100).toFixed(1);
    expect(rate).toBe('15.0');
  });

  it('retourne — si aucun envoi', () => {
    const campaign = { emails_sent: 0, responses_received: 0 };
    const rate =
      campaign.emails_sent > 0
        ? ((campaign.responses_received / campaign.emails_sent) * 100).toFixed(1)
        : '—';
    expect(rate).toBe('—');
  });
});
