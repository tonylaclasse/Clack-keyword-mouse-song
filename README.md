# Clack

Le bruit d'un clavier mécanique et d'un clic de souris, depuis la barre de menus du Mac.

## Installer

macOS 13 ou plus récent, sur Mac Intel comme Apple Silicon. Il faut les outils de
développement d'Apple, gratuits, une seule fois :

```
xcode-select --install
```

Puis, dans le dossier du projet :

```
./build.sh
```

Le script compile l'app, la copie dans `/Applications` et la lance. Elle n'a pas
d'icône dans le Dock ni de fenêtre : tout se passe depuis l'icône clavier en haut
à droite. S'il y avait déjà une version installée, elle est remplacée.

Construire l'app soi-même évite le blocage de macOS sur les apps téléchargées
sans certificat Apple.

## L'autorisation, à faire une fois

macOS interdit à toute app d'entendre le clavier tant qu'on ne l'a pas autorisée.

1. Réglages Système, Confidentialité et sécurité, **Surveillance de la saisie**
2. Cocher **Clack**

Tant que ce n'est pas fait, le menu affiche « Autoriser dans Réglages Système ».
Une fois coché, le son démarre dans les deux secondes, sans relancer l'app.

Dans un champ mot de passe, macOS coupe l'accès au clavier : silence total. C'est
voulu par le système.

C'est la même autorisation qu'un logiciel espion, alors autant être clair : Clack
ne retient rien, n'écrit rien sur le disque et ne se connecte à aucun réseau. Il
demande au système la permission d'écouter seulement, jamais de modifier une
frappe. Tout tient dans un fichier de 417 lignes, `Sources/main.swift`, lisible
en dix minutes.

## Le menu

- **Sons activés** : coupe tout d'un clic
- **Clavier** : dix ambiances — Thock (profond), Clack (claquant), Feutré (discret),
  Machine à écrire, Crème (doux et rond), Marbre (aigu et net), Ressort (IBM Model M),
  Portable (plat et fin), Bois (chaud et creux), Bulle (tout en pop)
- **Clic de souris** : dix clics au choix — classique, doux, sec, lourd, rétro,
  gaming, tic, claquant, creux, trackpad — ou *Aucun* pour n'entendre que le clavier
- **Volume**
- **Lancer au démarrage**

Chaque son existe en trois variantes tirées au hasard, avec un volume légèrement
différent à chaque frappe : deux touches ne sonnent jamais exactement pareil. La
barre d'espace a son propre son, plus grave, comme sur un vrai clavier.

## Changer les sons

Les sons sont fabriqués par `tools/make_sounds.py` (aucune dépendance). Modifier
les recettes en haut du fichier, puis :

```
python3 tools/make_sounds.py && ./build.sh
```

Pour tester sans reconstruire l'app, déposer ses propres fichiers dans
`~/Library/Application Support/Clack/Sounds/`, en gardant la même arborescence
(`thock/down-1.wav`, `up-1.wav`, `space-1.wav`, etc.). L'app les prend en priorité,
et remplace alors *tous* les sons : ce dossier doit contenir les packs voulus au
complet. Un dossier dont le nom commence par `mouse` est proposé comme clic de
souris et n'a pas besoin de `space-*.wav`.

## Reconstruire

Chaque `./build.sh` change l'identité de l'app aux yeux de macOS, donc l'autorisation
est à redonner. Le script efface l'ancienne pour qu'une nouvelle demande apparaisse
au lieu d'une case cochée qui ne marche plus. Un certificat Apple Developer ID
supprimerait cette étape.
