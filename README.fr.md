# indoor-geolocator

[English](README.md) · [简体中文](README.zh-CN.md) · [Português](README.pt-BR.md) · **Français** · [Español](README.es.md) · [日本語](README.ja.md) · [Deutsch](README.de.md)

Une skill pour agents qui détermine **où une photo d'intérieur a été prise** : une chambre d'hôtel, un
appartement, un restaurant, une boutique, une gare, un musée, une salle de classe, une voiture. Elle
renvoie le lieu, l'adresse, les coordonnées avec un rayon d'erreur et un niveau de confiance que les
preuves soutiennent réellement. Elle laisse aussi un dossier de cas bien rangé qui montre chaque étape du
raisonnement.

**Page du projet et démonstration interactive :** https://ezharjan.github.io/indoor-geolocator/

Joignez une photo et invoquez la skill. Aucun prompt n'est nécessaire. La réponse arrive dans la langue de
l'utilisateur et prend cette forme (les valeurs sont données à titre d'exemple) :

```
📍 <Lieu> — <adresse, ville, pays>
   51.044560, -114.064700 (WGS84) ± 60 m · niveau : site · confiance : MEDIUM
Pourquoi : ... les 2 à 4 preuves décisives, chacune avec sa source et la façon dont elle a été vérifiée
Vérifié par rapport à : ... les photos de référence comparées, les éléments concordants, le rival testé
Meilleure piste (non vérifiée) : ... un candidat plus fin, ses coordonnées (le point le plus probable) et le test qui le confirmerait
Alternatives : ... le second, sa probabilité et le test qui les départagerait
Non vérifié / limites : ... ce qui n'a pas pu être contrôlé et pourquoi
Dossier du cas : .../photo-geolocation (REPORT.md contient tout le raisonnement)
```

## Ce qu'elle fait

La skill donne au modèle une méthode de travail stricte, qui fait passer l'exactitude avant tout, et une
boîte à outils en ligne de commande (`scripts/igl.py`, Python 3.9+, Pillow). Chaque observation entre dans
un registre unique, et le classement comme la confiance sont calculés à partir de ce registre, pas
affirmés.

Les photos d'intérieur sont mal localisées pour une poignée de raisons, et la méthode est construite
autour d'elles : une pièce ressemblante est prise pour le lieu, le premier candidat plausible est gardé,
une sortie de machine (de l'OCR sur un tapis, l'étiquette d'un moteur, une recherche qui n'a jamais
tourné) est lue comme un fait, un objet transportable est lu comme le bâtiment, une enseigne est prise
pour une succursale, et la précision est inventée.

1. **Prise en charge.** Copie la photo octet pour octet. Lit EXIF, GPS, XMP, IPTC, ICC, la miniature
   intégrée (un recadrage ou une retouche s'y voit), le motif du nom de fichier, les marqueurs d'IA et
   les Content Credentials C2PA, et convertit le décalage UTC en fuseaux horaires. Vérifie en cinq
   secondes quels services en ligne la boîte à outils peut joindre.
2. **Les hypothèses d'abord.** Deux à quatre hypothèses classées sont consignées avant toute sortie
   d'outil (défense contre l'ancrage).
3. **Lire toute la photo.**
   - OCR filtré pour la précision (une texture n'est pas signalée comme du texte), codes QR et
     codes-barres avec interprétation du contenu (codes de paiement EMV, QR-factures suisses, SEPA, UPI,
     Wi-Fi, vCards, préfixes GS1), fouille du texte (téléphones jusqu'à la ville, domaines, prix, codes
     postaux, unités, termes fiscaux).
   - Un catalogue d'environ 200 indices, lu par l'agent sur des tuiles qui se chevauchent : porteurs
     d'identité (noms, œuvres uniques, la vue), normes fixes (prises, interrupteurs, plomberie,
     signalétique de sécurité) et références locales (un tableau d'un monument local, une carte, un
     dépliant).
4. **Trouver des candidats.**
   - **Recherche d'image inversée** sans interface sur Yandex, TinEye et Baidu, avec Google Lens et Bing
     via un outil de navigation. Chaque résultat est comparé à la photo et classé **COPY** (la même
     photographie : provenance), **SAME SCENE** / **PARTIAL** (structure concordante) ou
     **unconfirmed**.
   - **Recherche d'images par texte** (`refs`) : recherches d'images pour un lieu, ou pour tous les
     lieux d'un type dans une zone. Les images sont comparées à la photo et présentées **de la plus
     ressemblante à la moins ressemblante** (DINOv2), si bien que le bon lieu ressort même quand aucune
     légende ne le décrit. Lors d'un test, deux recherches génériques de bars d'hôtel dans un État
     américain ont placé le vrai bar en tête parmi 100 images de bars différents.
   - Noms, téléphones, URL et noms de Wi-Fi avec la recherche web de l'agent lui-même ; normes fixes
     croisées sur 250 pays hors ligne ; tous les lieux d'un type énumérés depuis OpenStreetMap et
     Wikidata ; annonces et réseaux sociaux (centrés sur les lieux).
5. **Vérifier : la barrière entre une piste et une réponse.** Un test de réfutation est écrit d'abord.
   Les photos du candidat lui-même sont placées à côté de la photo, et des éléments fixes précis sont
   comptés (fenêtres, plafond, aménagements intégrés, la vue, œuvres créées pour le lieu ; le mobilier
   ne prouve qu'un style d'aménagement). Le rival le plus proche subit la même comparaison. Si le rival
   « concorde » aussi, les éléments relèvent d'un aménagement partagé : la concordance est enregistrée
   pour la zone du groupe, et les lieux restent des pistes.
6. **Cohérence.** Fuseau horaire, soleil, météo, saison et normes sont confrontés au candidat, on plaide
   la cause du second, et l'étape décisive est refaite autrement.
7. **Décision.** La réponse est le niveau le plus fin que les preuves vérifient. Un lieu non vérifié
   dans une zone vérifiée est signalé comme la meilleure piste, avec ses propres coordonnées (le point
   le plus probable), jamais comme la réponse. Le dossier du cas est finalisé et élagué.

### Règles d'exactitude inscrites dans le code

- **Plafonds par statut.** Le poids d'un indice est plafonné selon la façon dont il a été obtenu : une
  inférence ≤3, une observation ≤6, un témoignage tiers ≤10, des métadonnées de fichier ou une copie
  retracée de la photo ≤20, un texte lu sur un recadrage agrandi ou un résultat calculé ≤50, une
  concordance avec des images de référence indépendantes ≤100. L'étiquette d'un moteur est une piste
  (≤3), quoi qu'elle dise.
- **Indices identifiants et indices de catégorie.** Un indice décisif (un nom lu dans la photo, un code
  décodé, le GPS, une copie retracée, une référence concordante) identifie un seul lieu et est pesé
  contre toutes les alternatives réunies : LR 50 signifie environ 50 contre 1, quel que soit le nombre
  de rivaux listés. Un indice de catégorie (un type de prise, une langue, un style) concurrence chaque
  alternative une à une, de sorte que seuls plusieurs réunis tranchent un pays.
- **Concordances vérifiables.** Un indice `matched` doit nommer au moins trois éléments fixes précis et
  citer le fichier de comparaison. Une copie de la photo est refusée comme concordance : c'est une
  provenance, enregistrée comme `traced` avec sa page.
- **Le contrôle par le rival.** Une concordance avec une référence n'atteint HIGH que si un lieu rival a
  subi la même comparaison, ou si une seconde lignée décisive (un nom lu dans la photo, le GPS, une
  copie retracée) désigne le même lieu.
- **Un lieu exige un indice décisif.** La ressemblance, les étiquettes de moteurs et les légendes
  laissent un lieu à LOW, si nombreuses soient-elles à s'accorder : cette combinaison est exactement ce
  que produit un sosie.
- **Lignées indépendantes.** L'accord ne compte qu'entre sources indépendantes (image, text, metadata,
  web, engine, map, reference, geometry). Cinq indices de décoration forment une seule lignée.
- **Un tableau ouvert et cohérent.** Les alternatives non listées gardent une part à chaque niveau, une
  ville n'est jamais plus certaine que son pays, et une contradiction visant un pays bloque aussi HIGH
  pour l'hôtel qui s'y trouve.
- **Échec honnête.** Une recherche bloquée ou jamais lancée est signalée comme telle, jamais comme
  « aucun résultat ». Les images non confirmées ne sont jamais dites « différentes ».
- **Barrière de couverture.** Treize méthodes principales doivent chacune se terminer par results,
  no_results ou not_applicable avant que `check` passe ; `check` signale aussi un site sans comparaison
  avec des références ou sans rival, un rival qui a concordé lui aussi, et des recherches inversées
  qui n'ont jamais tourné.

## Installation

**claude.ai, Claude Desktop et Cowork.**
1. Assurez-vous que l'exécution de code est activée (*Settings → Capabilities*). L'accès réseau pour
   l'exécution de code aide (la boîte à outils joint alors elle-même les services de cartes et de
   recherche inversée) ; sans lui, l'agent effectue ces étapes avec ses propres outils de recherche
   web, de fetch et de navigation.
2. Ouvrez *Customize → Skills*, cliquez sur **+**, choisissez **+ Create skill → Upload a skill** et
   sélectionnez `indoor-geolocator.zip`.
3. Joignez une photo et invoquez la skill, ou demandez simplement « où cela a-t-il été pris ? ».

Le zip contient le dossier `indoor-geolocator/` à son niveau supérieur, comme l'exige l'envoi.

**Claude Code.** Copiez le dossier `indoor-geolocator/` dans `~/.claude/skills/` (tous les projets) ou
`<project>/.claude/skills/` (un projet). Invoquez-la avec `/indoor-geolocator`, ou laissez Claude s'en
saisir quand vous partagez une photo d'intérieur.

**Autres agents** (Codex, Gemini CLI, Cursor, …) : pointez l'agent vers `indoor-geolocator/SKILL.md`. La
boîte à outils est une simple CLI Python.

**Dépendances.** Pillow est requis, de même que `tzdata` sous Windows. Tout le reste est facultatif et ne
fait qu'activer la méthode correspondante.

```bash
pip install -r indoor-geolocator/requirements.txt             # Pillow (+ tzdata, nécessaire sous Windows)
pip install -r indoor-geolocator/requirements-optional.txt    # OpenCV + numpy, Playwright, onnxruntime, phonenumbers, HEIC, RapidOCR
playwright install chromium                                   # recherche inversée sans interface, recherche d'images, captures de pages
# Moteur d'OCR (recommandé) : tesseract avec ses packs de langues
#   apt install tesseract-ocr-all  |  brew install tesseract tesseract-lang  |  winget install UB-Mannheim.TesseractOCR
python indoor-geolocator/scripts/igl.py doctor                 # ce qui fonctionne ici, ce qui manque
```

Trois compléments comptent le plus pour l'exactitude : OpenCV (les tests COPY / SAME SCENE), Playwright
avec Chromium (recherche d'image inversée et recherche d'images) et onnxruntime (images triées par
ressemblance avec la photo). Le modèle de similarité (DINOv2 ViT-S/14, 24 Mo, Apache-2.0) ne fait pas
partie de la skill : il est téléchargé une fois depuis huggingface.co à la première utilisation et
contrôlé par un SHA-256. `IGL_NO_EMBED=1` le désactive.

## Utiliser directement la boîte à outils

```bash
IGL="python3 indoor-geolocator/scripts/igl.py"
$IGL init photo.jpg                                    # dossier du cas + métadonnées + grille + test du réseau
$IGL note CASE "Hypotheses: 1) ... 2) ..." --kind hypothesis --status inferred --source image
$IGL scan CASE                                         # OCR, QR/codes-barres, signaux textuels, tuiles de balayage
$IGL crop CASE --cell C3:D4 --enhance auto --label socket
$IGL revsearch CASE --cell B2:C3 --flip                # Yandex, TinEye, Baidu ; chaque résultat classé par rapport à la photo
$IGL share CASE --cell B2:C3                           # liens pour Google Lens et Bing (copie temporaire)
$IGL countries --plug G --currency £ --drive left --case CASE --clue N2
$IGL refs CASE "hotel lounge sea view Poole"           # images de toute une zone, les plus ressemblantes d'abord
$IGL geo poi --tag tourism=hotel --area "Poole" --case CASE --add site --parent C3
$IGL refs CASE "Hotel Name Poole lounge" --for C12     # les photos d'un candidat à côté de la vôtre
$IGL compare CASE --refs E14 --pick 3,7 --for C12      # grand côte à côte + tests de concordance
$IGL note CASE "Matches a traveller photo (2023)" --kind match --status matched --source reference --file E16 \
     --features "arched window pair; coffered ceiling 3x4; green marble fireplace" --for C12:60 --why "..."
$IGL refs CASE "Rival Hotel Poole lounge" --for C13    # le contrôle par le rival
$IGL rank CASE
$IGL answer CASE C12 --summary "..."
$IGL check CASE
$IGL finalize CASE
```

`$IGL <command> -h` documente chaque option. Sous Windows, utilisez `python` au lieu de `python3`. Les
coordonnées sud et ouest fonctionnent telles que saisies (`--at -33.86,151.21`).

## Ce que vous obtenez

```
photo-geolocation/
├── REPORT.md       la réponse, la meilleure piste, la confiance par niveau, les preuves, les candidats, la chronologie, les méthodes, le traitement des données
├── result.json     la même chose en JSON lisible par machine (schéma igl.result/1)
├── case.json       le registre complet : indices, candidats, liens, exclusions, tentatives, horodatages
├── input/          la photo (copie exacte) et metadata.json
└── evidence/       uniquement les recadrages, planches, vues de comparaison et captures que le registre cite
```

Le travail de brouillon (tuiles, caches, téléchargements) vit dans `.work/` et est supprimé par
`finalize`, qui retire aussi tout fichier de preuve que rien ne cite. Un dossier de cas existant n'est
jamais écrasé.

## Vie privée et usage responsable

- **Les personnes ne sont pas des cibles.** Aucune reconnaissance faciale et aucune identification
  d'individus.
  - Vêtements, uniformes, badges et objets personnels ne servent que pour ce qu'ils disent du lieu.
  - L'origine ethnique apparente est traitée comme un contexte faible et sujet aux biais, jamais comme
    une exclusion.
  - Les réseaux sociaux sont interrogés sur des lieux, du texte, des tags et la photo elle-même,
    jamais sur des personnes ou des auteurs de publications.
- **Domiciles privés.** Pour une résidence privée identifiable sans finalité déclarée, la skill demande
  une fois à quoi servira le résultat. Sans finalité légitime, elle s'arrête au niveau de la ville ou
  du quartier.
- **Caviardage.** Les noms de particuliers et les adresses de domicile sont écartés des rapports. Les
  mots de passe Wi-Fi, les IBAN et les noms des cartes de contact sont caviardés partout où ils sont
  décodés ou renvoyés par un moteur ou une page.
- **Envois.** La recherche d'image inversée envoie la photo (métadonnées retirées) aux moteurs. `share`
  place une copie sans métadonnées sur un hébergeur temporaire (supprimée après 1 à 3 heures) pour Lens
  et Bing, et `revsearch` fait de même de lui-même quand le formulaire d'envoi d'un moteur échoue
  (`--no-share` l'empêche). Le rapport liste chaque moteur et chaque copie temporaire. `refs` n'envoie
  que du texte de recherche, et le modèle de similarité tourne en local. Préférez des recadrages sans
  personnes ; rien n'est envoyé sans demander quand l'utilisateur signale une photo comme privée.
- **Services.** La skill respecte les politiques des services (Nominatim ≤1 requête/s, requêtes
  Overpass bornées, User-Agent identifiable). Elle ne se connecte jamais au nom de quiconque, ne résout
  jamais de CAPTCHA et ne collecte jamais en masse. Clés facultatives de l'utilisateur : `SERPAPI_KEY`
  pour Google Lens dans `revsearch`, `WIGLE_API_NAME` / `WIGLE_API_TOKEN` pour les recherches de SSID
  Wi-Fi. `IGL_USER_AGENT` définit un User-Agent personnalisé.

Les résultats de géolocalisation sont des estimations pondérées par les preuves, pas des certitudes.
Lisez la confiance, la meilleure piste et la ligne « non vérifié » avant d'agir sur une réponse.

## Organisation du dépôt

```
.
├── indoor-geolocator/          LA skill (c'est ce dossier qui s'installe)
│   ├── SKILL.md                méthode de travail, règles de preuve, conduite, format de réponse
│   ├── LICENSE.txt             copie de LICENSE (le zip est livré sans la racine du dépôt)
│   ├── requirements*.txt
│   ├── references/             catalogue d'indices, guides de scènes et de recherche, fenêtre/lumière, vérification,
│   │                           preuves et confiance, sources et outils
│   ├── scripts/igl.py          la CLI ; scripts/iglib/ contient ses modules
│   └── data/                   countries.json, gs1_prefixes.json (+ README avec sources et licences)
├── indoor-geolocator.zip       la même skill, empaquetée pour l'envoi
├── build_skill_zip.py          reconstruit et vérifie le zip (à lancer après chaque modification de la skill)
├── tools/build_data.py         outil de maintenance : reconstruit data/ depuis Unicode CLDR et Wikipédia
├── tools/make_demo.py          outil de maintenance : reconstruit docs/demo/ avec la version actuelle
├── tests/                      suite de tests hors ligne (pytest ; `pytest.ini` pointe dessus)
├── docs/                       page du projet (GitHub Pages) avec le cas de démonstration publié
├── LICENSE
├── README.md                   ce README en anglais
└── README.*.md                 traductions (zh-CN, pt-BR, fr, es, ja, de)
```

## Développement

```bash
python -m pytest                   # tests hors ligne : règles du registre, plafonds, concordance, classement, analyseurs, géométrie ;
                                   # et aussi docs vs CLI, le zip vs le dossier de la skill, la page du projet vs le cas de démonstration
python tools/build_data.py         # rafraîchit data/ (met les sources en cache dans .data-src/ ; --offline reconstruit depuis le cache)
python tools/make_demo.py          # reconstruit le cas de démonstration dans docs/demo/ avec la version actuelle
python build_skill_zip.py          # reconstruit indoor-geolocator.zip si le dossier a changé ; --check vérifie seulement
```

## Journal des modifications

### 2.0.0

La version de l'exactitude : conçue contre la mauvaise réponse la plus courante, un lieu sosie nommé avec
assurance.

- **Trouver.** Nouvelle commande `refs` : recherche d'images par texte (Brave, Startpage) et pages de
  galerie, chaque image étant comparée à la photo. Les images et les résultats de recherche inversée
  sont triés par similarité visuelle (DINOv2, facultatif), si bien que les références les plus
  probables sont les premières tuiles que voit l'agent.
- **Recherche inversée.** Chaque résultat est classé COPY / SAME SCENE / PARTIAL / unconfirmed par
  rapport à la photo. Une recherche jamais lancée est `unavailable`, pas `no_results` ; repli par URL
  quand un formulaire d'envoi échoue ; Google Lens facultatif via la clé SerpApi de l'utilisateur.
- **Vérification.** Les indices `matched` doivent nommer trois éléments et citer la comparaison ; les
  copies sont refusées comme concordances et enregistrées comme provenance `traced` ;
  `compare --refs E## --pick` ; le contrôle par le rival est exigé pour HIGH ; les concordances
  d'aménagement sont enregistrées pour la zone, les lieux restant des pistes.
- **Confiance.** Les indices décisifs sont pesés contre l'ensemble du champ (un lieu vérifié n'est plus
  dilué par les pays non listés ni par les rivaux que l'agent a énumérés) ; un lieu exige un indice
  décisif pour MEDIUM ; les étiquettes de moteurs sont plafonnées à 3 ; les contradictions bloquent
  HIGH tout le long de la chaîne ; un endroit est au moins aussi certain que l'endroit vérifié qu'il
  contient.
- **Lecture.** La sortie de l'OCR est filtrée pour la précision (fini le « texte » et les écritures
  exotiques lus sur les tapis et les plafonds) ; `scan` écrit une planche des recadrages de texte ;
  `crop --of` zoome dans n'importe quelle image de preuve.
- **Robustesse.** Repli sur Photon quand Overpass est injoignable, téléchargements avec nouvelles
  tentatives, signalement des limites de débit à chaque exécution, méthodes déduites des indices
  consignés, `log` avec des listes séparées par des virgules.
- **Sortie.** Un repère de meilleure estimation (les coordonnées de la piste quand la réponse est plus
  grossière), une section de vérification avec le contrôle par le rival dans le rapport, des tableaux
  de candidats qui disent ce qu'est chaque ligne (la réponse, un endroit qui la contient, la piste non
  vérifiée, les alternatives hors tableau), `tools/make_demo.py` pour reconstruire le cas de
  démonstration, et des tests qui maintiennent la page du projet fidèle à ce cas et le zip fidèle au
  dossier de la skill.

### 1.1.0

Ni étiquetée ni publiée séparément : ces changements sont publiés pour la première fois avec la 2.0.0.

- Méthode réordonnée autour des voies de concordance exacte et d'une barrière de vérification ;
  hypothèses avant la sortie des outils ; répartition entre la boîte à outils et les outils de
  recherche web, de fetch et de navigation de l'agent lui-même.
- Notation : un tableau ouvert à chaque niveau, des parts cohérentes le long de la chaîne, pas de
  remontée des indices de catégorie, barrière sur la réponse avec une meilleure piste séparée,
  contrôles avant le rapport.
- Recherche inversée : ajout de Baidu, planches-contact d'images similaires, `share` pour Lens et Bing
  par URL.
- `compare` : tests de quasi-doublon, de même photographie et géométriques SIFT/RANSAC, avec pièces en
  miroir.
- Test du réseau dans `init` ; `geo ... --print-url` ; `note --for/--against` en un seul appel ;
  lecteur C2PA.

### 1.0.0

Première version publique.

## Licence

Le code et la documentation sont publiés sous la [MIT License](LICENSE). Les fichiers de données de
`indoor-geolocator/data/` conservent les licences de leurs sources :
- Champs Unicode CLDR : [Unicode License v3](https://www.unicode.org/license.txt).
- Champs dérivés de Wikipédia (types de prises, secteur, sens de circulation, numéros d'urgence,
  préfixes GS1) : [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), © contributeurs de
  Wikipédia.

Les détails se trouvent dans [indoor-geolocator/data/README.md](indoor-geolocator/data/README.md).

Des idées de conception ont été adaptées des projets open source geo-sleuth, Geo-Guesser et
Searching-skill : des règles imposées dans le code, un tableau de candidats à rapports de vraisemblance,
des preuves graduées par lignée, une barrière de couverture des méthodes, « la machine classe d'abord »
avec un ordre de similarité DINOv2, et une vérification SIFT/RANSAC. Le modèle de similarité est DINOv2
(Meta AI, Apache-2.0) dans l'export ONNX publié sous le nom `Xenova/dinov2-small` ; il est téléchargé à
l'exécution et n'est pas redistribué ici.
