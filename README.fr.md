<p align="center"><img src="logo.png" alt="RoomFlow" width="420"></p>

[🇬🇧 English](README.md) | [🇸🇪 Svenska](README.sv.md) | [🇳🇴 Norsk](README.no.md) | [🇫🇮 Suomi](README.fi.md) | [🇩🇰 Dansk](README.da.md) | [🇩🇪 Deutsch](README.de.md) | **🇫🇷 Français** | [🇳🇱 Nederlands](README.nl.md)

<p align="center">
  <a href="https://buymeacoffee.com/h7jyzdywm9s"><img src="https://img.shields.io/badge/Buy%20me%20a%20coffee-FFDD00?style=flat&logo=buy-me-a-coffee&logoColor=black" alt="Buy Me A Coffee"></a>
</p>

---

# RoomFlow

Contrôlez les lumières et prises par pièce en fonction de l'heure de la
journée — avec des dérogations week-end/absence optionnelles, des temps de
transition, des liaisons de boutons physiques et une automatisation basée
sur le mouvement/les seuils. Conçu pour Home Assistant comme une
intégration personnalisée, accompagnée d'une carte Lovelace qui fonctionne
aussi comme une page complète du panneau latéral.

## Pourquoi

La plupart des configurations d'éclairage basées sur l'heure de la journée
finissent par devenir un tas d'automatisations pénibles à ajuster. RoomFlow
vous offre un seul endroit pour définir, par pièce et par appareil : *que
doit faire cette lumière/prise le matin, dans la journée, le soir, la nuit
— et cela change-t-il le week-end ou quand personne n'est à la maison ?*
Puis ajoute par-dessus des boutons physiques et des déclencheurs de
mouvement/capteurs.

## Fonctionnalités

- **Planification selon l'heure de la journée** — définissez le
  comportement (allumé/éteint, luminosité, température de couleur) par
  appareil pour autant de périodes que vous voulez. Les périodes (matin/
  journée/après-midi/soir/nuit par défaut) forment une liste entièrement
  modifiable par l'utilisateur et ordonnée par priorité : ajoutez,
  supprimez, renommez et réorganisez-les librement depuis la carte. Chaque
  période peut combiner n'importe laquelle des 5 sources à la fois,
  cochées indépendamment : un **horaire fixe** intégré (une heure de
  début), la **position du soleil** (un événement solaire - aube/lever du
  soleil/midi solaire/coucher du soleil/crépuscule - plus un décalage), un
  **capteur de luminosité** (un seuil en lux), un **booléen existant**
  (pointez vers un `binary_sensor`/`input_boolean` que vous avez déjà —
  "allumé" signifie qu'il est actif), ou un **capteur existant** (associez
  l'une de ses valeurs d'état à celle-ci, afin que cela fonctionne avec
  n'importe quel capteur d'heure de la journée dans n'importe quelle
  langue). Une période est active si N'IMPORTE LAQUELLE de ses sources
  activées le dit actuellement (logique OU). La période "actuelle" est
  déterminée par ordre de priorité : la première période active dans la
  liste (en haut = priorité la plus élevée) l'emporte — vous pouvez donc
  librement mélanger les types de sources (par ex. une période basée sur la
  luminosité au-dessus d'une période basée sur l'horaire pour laisser
  l'obscurité l'emporter sur l'horloge). Une fois semaine/week-end configuré
  (voir ci-dessous), les sources horaire fixe et position du soleil peuvent
  chacune définir une heure/un événement solaire différent pour le
  week-end — par ex. le matin peut commencer plus tard le samedi et le
  dimanche — sans avoir besoin d'une période entièrement séparée pour cela.
- **Dérogations week-end et absence** (optionnel) — pour chacune, choisissez
  un capteur existant (un simple `binary_sensor` allumé/éteint fonctionne
  aussi — indiquez simplement à RoomFlow quelle polarité "allumé" signifie
  pour semaine/week-end), une option intégrée (choisissez quels jours de la
  semaine comptent comme week-end ; choisissez une ou plusieurs entités
  `person.*` pour présent/absent), ou laissez-la inutilisée. Ces deux choix,
  et la source d'heure de la journée ci-dessus, sont entièrement
  indépendants — mélangez librement. Remplacez le comportement par défaut
  pour des appareils spécifiques le week-end ou en cas d'absence. Priorité :
  **absence > week-end > par défaut**.
- **Conditions personnalisées par pièce** — au-delà des axes week-end/
  absence à l'échelle de la maison, chaque pièce peut définir sa propre
  liste ordonnée de conditions (un nom + une entité + l'état signifiant
  qu'elle est active), vérifiées par ordre de priorité *au-dessus* de
  absence/week-end/par défaut. Chaque condition obtient sa propre variante
  de comportement par période (matin/journée/après-midi/soir/nuit) et par
  appareil, exactement comme week-end/absence — utile pour un comportement
  lié à quelque chose de spécifique à cette pièce (par ex. la présence
  d'une personne en particulier) plutôt qu'à l'état de toute la maison.
- **Temps de transition** — une valeur par défaut globale par période,
  modifiable par appareil/période.
- **Boutons physiques** — liez n'importe quelle entité (par ex. un bouton
  Zigbee apparaissant comme une entité `event` ou `sensor`) à une action :
  basculer la pièce, l'éteindre, exécuter immédiatement le comportement
  programmé, ou forcer une période spécifique quelle que soit l'heure
  réelle.
- **Déclencheurs de mouvement et de seuil par pièce** — combinez plusieurs
  conditions avec une logique OU : capteurs de mouvement et/ou capteurs de
  seuil numériques (par ex. "humidité supérieure à 65 %"). La pièce est
  considérée comme "active" dès qu'une condition est vraie, exécute
  immédiatement son comportement programmé, et chaque appareil activé par
  le mouvement (choisi par appareil, avec son propre délai d'extinction qui
  remplace celui par défaut de la pièce) s'éteint à nouveau lorsque plus
  rien n'est vrai — en option en tamisant d'abord à une faible luminosité
  comme avertissement (un mouvement pendant cette fenêtre restaure la pleine
  luminosité au lieu d'éteindre). Un appui sur un bouton physique verrouille
  cet appareil hors du contrôle par mouvement jusqu'au prochain cycle de
  mouvement frais, afin qu'il ne soit pas immédiatement outrepassé.
- **Interface de la carte** — gérez *tout* (pièces, appareils, boutons,
  mouvement et tous les réglages heure de la journée/semaine-week-end/
  présent-absent ci-dessus) depuis une carte personnalisée à onglets, soit
  intégrée dans un tableau de bord, soit comme sa propre page de panneau
  latéral enregistrée automatiquement. Rien n'est configuré via l'assistant
  intégré "Ajouter une intégration" de Home Assistant — cette étape ajoute
  simplement RoomFlow en un seul clic ; tout le reste se trouve dans
  l'onglet Paramètres de la carte et s'applique instantanément, sans
  redémarrage nécessaire.
- **État en direct et test manuel** — voyez l'état actuel réel de chaque
  appareil, et déclenchez "tester maintenant" par pièce ou pour tout à la
  fois.
- **Diagnostics** — téléchargez un fichier de diagnostic (Paramètres →
  Appareils et services → RoomFlow → Télécharger les diagnostics) pour les
  rapports de bugs, sans exposer vos entity_id d'appareils spécifiques.
- **Exposé comme de véritables entités** — RoomFlow crée trois entités
  sensor ordinaires (période actuelle, type de jour, état de présence) plus
  un binary_sensor par période (matin/journée/après-midi/soir/nuit —
  "allumé" exactement quand cette période est celle actuellement en
  vigueur, quelle que soit la ou les sources qui l'ont déterminé) qui
  apparaissent comme n'importe quelle autre entité : utilisables dans vos
  propres automatisations/tableaux de bord. Leur nom d'appareil et leur
  zone sont définis depuis l'onglet Paramètres de la carte, pas besoin de
  les rechercher ensuite dans Entités.
- **Résilient** — un appareil en échec enregistre un avertissement au lieu
  de bloquer le reste de la pièce.

## Installation

### Via HACS (dépôt personnalisé)

1. HACS → Intégrations → menu à trois points → **Dépôts personnalisés**
2. Ajoutez l'URL de ce dépôt, catégorie **Integration**
3. Installez "RoomFlow", redémarrez Home Assistant

### Manuelle

1. Copiez `custom_components/roomflow` dans `config/custom_components/`
   (la carte est intégrée dedans, dans `custom_components/roomflow/www/` —
   aucune copie séparée nécessaire)
2. Redémarrez Home Assistant

### Configuration

1. **Paramètres → Appareils et services → Ajouter une intégration →
   RoomFlow** — il n'y a rien à remplir, confirmez simplement. Tout le
   reste se passe dans la carte.

   RoomFlow sert sa propre carte et l'enregistre automatiquement — aucune
   copie dans `config/www` ni entrée manuelle dans **Paramètres → Tableaux
   de bord → Ressources** n'est nécessaire. Elle s'ajoute aussi elle-même
   comme page dans le panneau latéral. Vous pouvez aussi ajouter la carte
   manuellement à un tableau de bord :
   ```yaml
   type: custom:roomflow-card
   ```
2. Ouvrez la carte RoomFlow (panneau latéral ou tableau de bord) → onglet
   **⚙ Paramètres**, et configurez :
   - **Périodes de la journée** — une liste ordonnée (en haut = priorité
     la plus élevée), à partir des 5 valeurs par défaut (matin/journée/
     après-midi/soir/nuit). Ajoutez, supprimez, renommez ou réorganisez
     (↑/↓) librement. Chaque période peut cocher n'importe quelle
     combinaison des 5 sources — elle est active si N'IMPORTE LAQUELLE de
     celles cochées le dit actuellement (logique OU) :
     - Horaire fixe : une heure de début.
     - Position du soleil : un événement solaire (aube/lever du soleil/
       midi solaire/coucher du soleil/crépuscule) + un décalage optionnel
       en minutes.
     - Luminosité : un capteur de lux + un seuil en lux.
     - Booléen existant : un `binary_sensor`/`input_boolean` qui est
       "allumé" exactement quand cette période doit être active.
     - Capteur existant : une entité + la valeur d'état signifiant que
       cette période est active (fonctionne avec n'importe quel capteur
       d'heure de la journée, dans n'importe quelle langue).
     La période actuelle est celle qui se trouve le plus haut dans la liste
     et qui est actuellement active. Une fois Semaine/week-end configuré
     ci-dessous, Horaire fixe et Position du soleil bénéficient chacun d'une
     exception de week-end facultative — une heure de début ou un événement
     solaire distinct, uniquement pour les jours de week-end.
   - **Semaine/week-end** et **Présent/absent** — chacun soit "non utilisé",
     un capteur existant, ou une option intégrée (case à cocher par jour de
     la semaine ; une ou plusieurs entités `person.*`), indépendamment de
     tout le reste.
   - **Appareil** — nom et zone pour les propres capteurs de RoomFlow.

   Chaque changement ici s'applique instantanément — aucun redémarrage,
   rien à enregistrer séparément.

## Fonctionnement

Chaque pièce contient des appareils (lumières/prises). Chaque appareil a un
comportement par période, choisi dans cet ordre lorsque RoomFlow
l'applique :

1. Dérogation **Absence**, si activée pour cette période et que la source
   présent/absent rapporte actuellement "absent"
2. Dérogation **Week-end**, si activée pour cette période et que la source
   semaine/week-end rapporte actuellement une valeur de week-end
3. Comportement **Par défaut**

RoomFlow réapplique automatiquement dès qu'une source configurée change :
les entrées basées sur des capteurs réagissent aux changements d'état,
celles intégrées réagissent à leur propre horloge (une limite d'horaire,
ou minuit pour la sélection des jours de la semaine) — et il réagit aussi
immédiatement aux appuis sur les boutons et aux déclencheurs de mouvement/
seuil que vous avez configurés.

## Contribuer

Les rapports de bugs et les pull requests sont les bienvenus. C'est un
projet relativement jeune — attendez-vous à quelques aspérités, en
particulier autour des combinaisons de conditions plus avancées et des
types d'appareils supplémentaires (climate, media_player, etc. sont des
prochaines étapes naturelles).

## Langues prises en charge

English (en), Svenska (sv), Norsk (no), Suomi (fi), Dansk (da), Deutsch (de), Français (fr), Nederlands (nl) —
ce README, l'interface propre de la carte et le config flow suivent tous
les mêmes 8 langues. La carte choisit sa langue automatiquement selon le
paramètre de langue de Home Assistant.

## Licence

MIT — voir [LICENSE](LICENSE).
