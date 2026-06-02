"""Contexte métier pur utilisé par la génération IA."""

from datetime import date

from app.models.lead import Lead

REGIONAL_CONTEXT = {
    "06": "Côte d'Azur, tourisme balnéaire, soleil, plages, luxe, croisières",
    "13": "Provence, calanques, tourisme culturel, gastronomie méditerranéenne",
    "83": "Var, plages, Saint-Tropez, tourisme balnéaire et viticole",
    "34": "Hérault, plages méditerranéennes, Canal du Midi, oenotourisme",
    "30": "Gard, Pont du Gard, Cévennes, Camargue",
    "11": "Aude, Carcassonne, cathares, vignobles",
    "66": "Pyrénées-Orientales, Collioure, côte Vermeille, montagne et mer",
    "33": "Gironde, Bordeaux, vignobles, Bassin d'Arcachon, surf",
    "40": "Landes, surf, forêt, thermalisme, tourisme nature",
    "64": "Pays Basque, Béarn, montagne, surf, gastronomie basque",
    "17": "Charente-Maritime, La Rochelle, île de Ré, tourisme balnéaire",
    "85": "Vendée, Puy du Fou, côte atlantique, tourisme familial",
    "44": "Loire-Atlantique, Nantes, La Baule, tourisme urbain et balnéaire",
    "56": "Morbihan, Golfe du Morbihan, mégalithes, îles",
    "29": "Finistère, Bretagne sauvage, phares, pointe du Raz",
    "22": "Côtes-d'Armor, Côte de Granit Rose, tourisme nature",
    "35": "Ille-et-Vilaine, Saint-Malo, Mont-Saint-Michel",
    "73": "Savoie, stations de ski, thermalisme, lacs alpins",
    "74": "Haute-Savoie, Chamonix, Annecy, ski et randonnée alpine",
    "38": "Isère, Grenoble, Vercors, ski et randonnée",
    "05": "Hautes-Alpes, Serre Chevalier, Briançon, sports outdoor",
    "04": "Alpes-de-Haute-Provence, Gorges du Verdon, lavande",
    "65": "Hautes-Pyrénées, Lourdes, Pic du Midi, ski pyrénéen",
    "09": "Ariège, grottes, préhistoire, montagne pyrénéenne",
    "63": "Puy-de-Dôme, volcans d'Auvergne, thermalisme",
    "15": "Cantal, Salers, volcans, tourisme vert",
    "75": "Paris, tourisme urbain, monuments, shopping, gastronomie",
    "77": "Seine-et-Marne, Disneyland Paris, Fontainebleau",
    "78": "Yvelines, Versailles, tourisme culturel",
    "14": "Calvados, plages du débarquement, Deauville, fromages",
    "50": "Manche, Mont-Saint-Michel, Cherbourg, cotentin",
    "76": "Seine-Maritime, Étretat, Rouen, falaises",
    "37": "Indre-et-Loire, Châteaux de la Loire, gastronomie, vignobles",
    "41": "Loir-et-Cher, Chambord, châteaux, Sologne",
    "45": "Loiret, Orléans, forêt d'Orléans",
    "2A": "Corse-du-Sud, Ajaccio, Bonifacio, plages paradisiaques",
    "2B": "Haute-Corse, Bastia, Calvi, maquis, montagnes",
    "20": "Corse, île de beauté, plages, maquis, montagnes",
    "971": "Guadeloupe, Caraïbes, plages tropicales",
    "972": "Martinique, Caraïbes, plages tropicales",
    "973": "Guyane, Amazonie, tourisme d'aventure",
    "974": "La Réunion, volcans, randonnée tropicale",
}

CITY_CONTEXT = {
    "nice": "Côte d'Azur, tourisme balnéaire, soleil, plages, luxe",
    "cannes": "Côte d'Azur, festivals, plages, luxe, croisettes",
    "marseille": "Provence, calanques, tourisme culturel, port méditerranéen",
    "paris": "Tourisme urbain, monuments, shopping, gastronomie",
    "lyon": "Gastronomie, patrimoine UNESCO, tourisme urbain",
    "bordeaux": "Vignobles, gastronomie, architecture, fleuve",
    "biarritz": "Surf, Pays Basque, plages, thalasso",
    "chamonix": "Montagne, ski, alpinisme, Mont-Blanc",
    "annecy": "Lac, montagnes, vieille ville, sports nautiques",
    "strasbourg": "Alsace, marché de Noël, patrimoine, gastronomie",
    "ajaccio": "Corse, plages, Napoléon, maquis",
    "bastia": "Corse, port, Cap Corse",
    "lourdes": "Pèlerinage, Pyrénées, thermalisme",
    "saint-malo": "Côte d'Émeraude, corsaires, remparts, plages",
    "la rochelle": "Port, îles, tourisme balnéaire atlantique",
    "arcachon": "Bassin, dune du Pilat, huîtres, plages",
}

TYPE_LABELS = {
    "hotel": "hôtel",
    "camping": "camping",
    "gite": "gîte",
    "chambre_hotes": "chambre d'hôtes",
    "residence": "résidence de tourisme",
    "activite": "prestataire d'activités",
    "other": "établissement",
}

SEASONAL_CONTEXTS = {
    1: {
        "hook": "les voyageurs planifient déjà leurs vacances d'été — les réservations anticipées commencent",
        "urgency": "C'est souvent en janvier que les décisions se prennent pour la saison.",
        "angle": "période creuse = moment idéal pour travailler sa visibilité avant la reprise",
    },
    2: {
        "hook": "les vacances d'hiver battent leur plein et les premières réservations de printemps arrivent",
        "urgency": "Les voyageurs qui cherchent pour mars-avril comparent les offres maintenant.",
        "angle": "fenêtre courte avant la reprise printanière",
    },
    3: {
        "hook": "la saison approche — les premières recherches pour mai et l'été s'accélèrent",
        "urgency": "Les établissements qui apparaissent bien en ligne maintenant captent ces réservations anticipées.",
        "angle": "dernier moment pour se préparer avant l'ouverture de saison",
    },
    4: {
        "hook": "les beaux jours arrivent, les ponts de mai approchent et les premières réservations d'été sont en cours",
        "urgency": "Beaucoup de voyageurs cherchent leurs destinations de mai et de l'été en ce moment même.",
        "angle": "les ponts de mai (1er, 8 mai, Ascension) génèrent un pic de recherches dès maintenant",
    },
    5: {
        "hook": "les ponts de mai et le début de saison estivale — les réservations de juillet-août sont en plein boom",
        "urgency": "C'est maintenant que les voyageurs réservent pour l'été.",
        "angle": "début de haute saison, chaque semaine compte",
    },
    6: {
        "hook": "l'été est là, les recherches de dernière minute s'intensifient",
        "urgency": "Les voyageurs qui n'ont pas encore réservé cherchent des disponibilités en temps réel.",
        "angle": "dernière fenêtre pour capter les réservations estivales",
    },
    7: {
        "hook": "pleine saison — le pic de fréquentation bat son plein",
        "urgency": "Peu de temps pour changer les choses maintenant, mais c'est le bon moment pour préparer la prochaine saison.",
        "angle": "anticiper l'après-saison et la rentrée",
    },
    8: {
        "hook": "pic estival — et déjà les premières recherches pour septembre et l'automne",
        "urgency": "Les early-adopters planifient leur automne maintenant.",
        "angle": "préparer la fin de saison et l'automne",
    },
    9: {
        "hook": "la rentrée arrive, et avec elle les premières recherches pour la Toussaint et les vacances d'automne",
        "urgency": "C'est le bon moment pour faire le bilan de saison et se préparer pour l'année prochaine.",
        "angle": "rentrée = moment idéal pour investir dans sa présence en ligne avant la prochaine saison",
    },
    10: {
        "hook": "les vacances de la Toussaint approchent et les premières réservations de Noël commencent",
        "urgency": "Les familles planifient leurs fêtes et séjours d'hiver maintenant.",
        "angle": "fenêtre entre deux saisons — moment idéal pour travailler le fond",
    },
    11: {
        "hook": "les fêtes de fin d'année approchent — réveillons, marchés de Noël, séjours hivernaux",
        "urgency": "Les réservations de décembre et janvier sont en cours.",
        "angle": "anticiper la nouvelle année et la prochaine saison",
    },
    12: {
        "hook": "fin d'année — et les bonnes résolutions pour la saison prochaine se prennent maintenant",
        "urgency": "C'est en décembre que les professionnels investissent dans ce qui va changer leur saison à venir.",
        "angle": "nouvelle année = nouvelle visibilité, c'est le moment d'agir",
    },
}


def get_seasonal_context() -> dict:
    """Retourne le contexte saisonnier courant."""
    return SEASONAL_CONTEXTS.get(date.today().month, SEASONAL_CONTEXTS[4])


def get_regional_context(lead: Lead) -> str:
    """Détermine le contexte touristique régional à partir du code postal."""
    if lead.postal_code and len(lead.postal_code) >= 2:
        department = lead.postal_code[:2]
        if lead.postal_code.startswith("20"):
            department = "20"
        if lead.postal_code.startswith("97") and len(lead.postal_code) >= 3:
            department = lead.postal_code[:3]

        context = REGIONAL_CONTEXT.get(department)
        if context:
            return context

    city = (lead.city or "").lower()
    for city_name, context in CITY_CONTEXT.items():
        if city_name in city:
            return context

    if lead.region:
        return f"Région {lead.region}"

    return ""


def get_type_label(lead: Lead) -> str:
    """Retourne un label lisible pour le type d'établissement."""
    lead_type = lead.lead_type.value if lead.lead_type else "other"
    return TYPE_LABELS.get(lead_type, "établissement")
