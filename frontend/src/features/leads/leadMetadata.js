export const TYPE_LABELS = {
  hotel: 'Hôtel',
  camping: 'Camping',
  gite: 'Gîte',
  residence: 'Résidence',
  chambre_hotes: "Ch. d'hôtes",
  activite: 'Activité',
  other: 'Autre',
};

export const TYPE_EMOJI = {
  hotel: '🏨',
  camping: '⛺',
  gite: '🏡',
  residence: '🏢',
  chambre_hotes: '🛏️',
  activite: '🎯',
  other: '🏠',
};

export const DEPT_NAMES = {
  '01': 'Ain',
  '02': 'Aisne',
  '03': 'Allier',
  '04': 'Alpes-de-Haute-Provence',
  '05': 'Hautes-Alpes',
  '06': 'Alpes-Maritimes',
  '07': 'Ardèche',
  '08': 'Ardennes',
  '09': 'Ariège',
  10: 'Aube',
  11: 'Aude',
  12: 'Aveyron',
  13: 'Bouches-du-Rhône',
  14: 'Calvados',
  15: 'Cantal',
  16: 'Charente',
  17: 'Charente-Maritime',
  18: 'Cher',
  19: 'Corrèze',
  '2A': 'Corse-du-Sud',
  '2B': 'Haute-Corse',
  21: "Côte-d'Or",
  22: "Côtes-d'Armor",
  23: 'Creuse',
  24: 'Dordogne',
  25: 'Doubs',
  26: 'Drôme',
  27: 'Eure',
  28: 'Eure-et-Loir',
  29: 'Finistère',
  30: 'Gard',
  31: 'Haute-Garonne',
  32: 'Gers',
  33: 'Gironde',
  34: 'Hérault',
  35: 'Ille-et-Vilaine',
  36: 'Indre',
  37: 'Indre-et-Loire',
  38: 'Isère',
  39: 'Jura',
  40: 'Landes',
  41: 'Loir-et-Cher',
  42: 'Loire',
  43: 'Haute-Loire',
  44: 'Loire-Atlantique',
  45: 'Loiret',
  46: 'Lot',
  47: 'Lot-et-Garonne',
  48: 'Lozère',
  49: 'Maine-et-Loire',
  50: 'Manche',
  51: 'Marne',
  52: 'Haute-Marne',
  53: 'Mayenne',
  54: 'Meurthe-et-Moselle',
  55: 'Meuse',
  56: 'Morbihan',
  57: 'Moselle',
  58: 'Nièvre',
  59: 'Nord',
  60: 'Oise',
  61: 'Orne',
  62: 'Pas-de-Calais',
  63: 'Puy-de-Dôme',
  64: 'Pyrénées-Atlantiques',
  65: 'Hautes-Pyrénées',
  66: 'Pyrénées-Orientales',
  67: 'Bas-Rhin',
  68: 'Haut-Rhin',
  69: 'Rhône',
  70: 'Haute-Saône',
  71: 'Saône-et-Loire',
  72: 'Sarthe',
  73: 'Savoie',
  74: 'Haute-Savoie',
  75: 'Paris',
  76: 'Seine-Maritime',
  77: 'Seine-et-Marne',
  78: 'Yvelines',
  79: 'Deux-Sèvres',
  80: 'Somme',
  81: 'Tarn',
  82: 'Tarn-et-Garonne',
  83: 'Var',
  84: 'Vaucluse',
  85: 'Vendée',
  86: 'Vienne',
  87: 'Haute-Vienne',
  88: 'Vosges',
  89: 'Yonne',
  90: 'Territoire de Belfort',
  91: 'Essonne',
  92: 'Hauts-de-Seine',
  93: 'Seine-Saint-Denis',
  94: 'Val-de-Marne',
  95: "Val-d'Oise",
  971: 'Guadeloupe',
  972: 'Martinique',
  973: 'Guyane',
  974: 'La Réunion',
  976: 'Mayotte',
};

export const TYPE_TABS = [
  {
    value: '',
    label: 'Tous',
    emoji: '📋',
    activeClass: 'bg-primary-800 text-white border-primary-800',
  },
  {
    value: 'hotel',
    label: 'Hôtels',
    emoji: '🏨',
    activeClass: 'bg-blue-600 text-white border-blue-600',
  },
  {
    value: 'camping',
    label: 'Campings',
    emoji: '⛺',
    activeClass: 'bg-green-600 text-white border-green-600',
  },
  {
    value: 'residence',
    label: 'Résidences',
    emoji: '🏢',
    activeClass: 'bg-violet-600 text-white border-violet-600',
  },
  {
    value: 'gite',
    label: 'Gîtes',
    emoji: '🏡',
    activeClass: 'bg-orange-500 text-white border-orange-500',
  },
  {
    value: 'chambre_hotes',
    label: "Ch. d'hôtes",
    emoji: '🛏️',
    activeClass: 'bg-pink-500 text-white border-pink-500',
  },
  {
    value: 'activite',
    label: 'Activités',
    emoji: '🎯',
    activeClass: 'bg-rose-500 text-white border-rose-500',
  },
  {
    value: 'nouvelle_entreprise',
    label: 'Nlles Entrep.',
    emoji: '🆕',
    activeClass: 'bg-emerald-600 text-white border-emerald-600',
  },
  {
    value: 'other',
    label: 'Autres',
    emoji: '🏠',
    activeClass: 'bg-slate-500 text-white border-slate-500',
  },
];

export const QUALIF_FILTERS = [
  { value: '', label: 'Tous' },
  { value: 'sans_site', label: '🔥 Sans site' },
  { value: 'a_analyser', label: '⚠️ À analyser' },
  { value: 'non_analyse', label: '❓ Non analysé' },
  { value: 'chaud', label: '🔥 Chaud' },
  { value: 'tiede', label: '😐 Tiède' },
  { value: 'froid', label: '❄️ Froid' },
];

export const STATUS_FILTERS = [
  { value: '', label: 'Tous les statuts' },
  { value: 'enriched', label: '✅ Enrichis' },
  { value: 'new', label: '🆕 Nouveaux' },
  { value: 'no_email', label: '📞 Contact alternatif' },
  { value: 'contacted', label: '📧 Contactés' },
  { value: 'responded', label: '💬 Ont répondu' },
  { value: 'interested', label: '⭐ Intéressés' },
];

export const STATUS_LABELS = {
  new: { label: 'Nouveau', cls: 'bg-slate-100 text-slate-600' },
  enriched: { label: 'Enrichi', cls: 'bg-blue-100 text-blue-700' },
  no_email: { label: '📞 Contacter autrement', cls: 'bg-orange-100 text-orange-700' },
  contacted: { label: 'Contacté', cls: 'bg-amber-100 text-amber-700' },
  responded: { label: 'A répondu', cls: 'bg-green-100 text-green-700' },
  converted: { label: 'Converti', cls: 'bg-emerald-100 text-emerald-700' },
  rejected: { label: 'Rejeté', cls: 'bg-red-100 text-red-600' },
};

export function getQualification(lead) {
  if (lead.is_nouvelle_entreprise && lead.rcs_score != null) {
    if (lead.rcs_score >= 5) {
      return {
        label: 'PRIORITAIRE',
        short: 'Prioritaire',
        bg: 'bg-emerald-100',
        text: 'text-emerald-700',
        dot: 'bg-emerald-500',
        border: 'border-emerald-200',
        emoji: '🔥',
      };
    }
    if (lead.rcs_score >= 3) {
      return {
        label: 'INTÉRESSANT',
        short: 'Intéressant',
        bg: 'bg-teal-50',
        text: 'text-teal-700',
        dot: 'bg-teal-400',
        border: 'border-teal-100',
        emoji: '👀',
      };
    }
    return {
      label: 'À QUALIFIER',
      short: 'À qualifier',
      bg: 'bg-slate-100',
      text: 'text-slate-600',
      dot: 'bg-slate-400',
      border: 'border-slate-200',
      emoji: '🔍',
    };
  }

  if (lead.has_website === false) {
    return {
      label: 'SANS SITE',
      short: 'Sans site',
      bg: 'bg-red-100',
      text: 'text-red-700',
      dot: 'bg-red-500',
      border: 'border-red-200',
      emoji: '🔥',
    };
  }

  const invalidUrls = ['', '-', 'n/a', 'na', 'none', 'null'];
  const hasValidUrl =
    lead.website &&
    !invalidUrls.includes(lead.website.toLowerCase().trim()) &&
    lead.website.trim().length > 3;

  if (!hasValidUrl && lead.has_website === null) {
    return {
      label: 'NON ANALYSÉ',
      short: 'Non analysé',
      bg: 'bg-slate-100',
      text: 'text-slate-600',
      dot: 'bg-slate-400',
      border: 'border-slate-200',
      emoji: '❓',
    };
  }

  if (hasValidUrl && lead.has_website === null && lead.website_quality_score === null) {
    return {
      label: 'À ANALYSER',
      short: 'À analyser',
      bg: 'bg-orange-100',
      text: 'text-orange-700',
      dot: 'bg-orange-400',
      border: 'border-orange-200',
      emoji: '⚠️',
    };
  }

  if (lead.score >= 70) {
    return {
      label: 'CHAUD',
      short: 'Chaud',
      bg: 'bg-red-50',
      text: 'text-red-600',
      dot: 'bg-red-400',
      border: 'border-red-100',
      emoji: '🔥',
    };
  }
  if (lead.score >= 40) {
    return {
      label: 'TIÈDE',
      short: 'Tiède',
      bg: 'bg-amber-50',
      text: 'text-amber-700',
      dot: 'bg-amber-400',
      border: 'border-amber-100',
      emoji: '😐',
    };
  }
  return {
    label: 'FROID',
    short: 'Froid',
    bg: 'bg-blue-50',
    text: 'text-blue-600',
    dot: 'bg-blue-400',
    border: 'border-blue-100',
    emoji: '❄️',
  };
}
