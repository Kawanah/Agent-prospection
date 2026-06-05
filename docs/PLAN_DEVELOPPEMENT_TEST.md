# Plan développement/test

Objectif : tester l'application sans envoi réel, corriger l'UI, puis valider les process métier avant toute phase de déploiement.

## Garde-fous actifs

- `APP_ENV=development`
- `ENABLE_EMAIL_DELIVERY=false`
- `ENABLE_AUTO_QUEUE=false`
- Aucun scheduler d'envoi automatique ne démarre tant que les deux flags email ne sont pas activés.
- Les boutons d'envoi affichent un mode simulation quand l'envoi réel est désactivé.

## Parcours à tester

1. Connexion administrateur.
2. Import de leads.
3. Affichage du tableau leads sur desktop et petit écran.
4. Enrichissement d'un lead.
5. Génération d'un brouillon email.
6. Mise en file d'un message sans traitement réel.
7. Simulation d'email de test.
8. Création et consultation d'une campagne.
9. Paramètres SMTP en mode simulation.

## Critères de validation UI

- Le tableau leads ne doit pas couper les colonnes.
- Le scroll horizontal doit apparaître quand la largeur manque.
- Les actions doivent rester accessibles.
- Les libellés ne doivent jamais laisser croire qu'un email réel part en mode test.

## Critères de validation emails

- Le message généré est un brouillon.
- Le ton reste calme, factuel et bienveillant.
- Pas de phrase agressive ou définitive.
- Pas de lien rendez-vous poussé par défaut.
- Pas d'envoi réel tant que `ENABLE_EMAIL_DELIVERY=false`.

## Passage vers préproduction

Avant d'activer un envoi réel :

1. Relire manuellement les brouillons générés.
2. Tester SMTP sur une adresse interne uniquement.
3. Activer `ENABLE_EMAIL_DELIVERY=true` temporairement.
4. Garder `ENABLE_AUTO_QUEUE=false` tant que le process humain n'est pas validé.
5. Activer l'auto-queue uniquement après validation explicite.
