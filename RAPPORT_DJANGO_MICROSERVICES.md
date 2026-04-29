# Rapport : Django et architecture microservices du projet Apex Motors

## 1. Introduction

Ce rapport décrit uniquement l’architecture présente dans ce projet. Le système est une application e-commerce de démonstration appelée **Apex Motors**. Elle permet de gérer des utilisateurs, des produits automobiles, des commandes et une recherche visuelle par image. Le projet est construit avec plusieurs applications **Django** séparées, chacune placée dans son propre service et exécutée dans son propre container Docker.

L’idée principale de l’architecture est de ne pas mettre toute la logique dans une seule application Django. Au lieu d’un monolithe, le projet utilise plusieurs microservices :

- `main_service` : passerelle principale et interface utilisateur.
- `user_service` : gestion des utilisateurs, profils et authentification JWT.
- `product_service` : gestion du catalogue, des catégories, des produits et des images.
- `order_service` : gestion des commandes et des snapshots de produits commandés.
- `search_service` : recherche visuelle, embeddings, indexation et communication avec Qdrant.

Chaque service Django possède sa propre configuration, ses propres routes, ses propres dépendances et sa propre base PostgreSQL. Le service de recherche utilise aussi **Qdrant**, une base vectorielle, pour stocker les embeddings des images de produits. Tous ces composants sont lancés avec `docker-compose.yml`, qui définit les containers, les ports, les variables d’environnement, les volumes et les dépendances entre services.

L’architecture du projet est donc organisée autour d’une séparation claire des responsabilités : l’authentification reste dans `user_service`, le catalogue reste dans `product_service`, les commandes restent dans `order_service`, et l’intelligence de recherche par image reste dans `search_service`. Le `main_service` sert surtout de point d’entrée pour l’utilisateur et coordonne les appels entre les autres services.

---

## 2. Rôle de Django dans le projet

Django est utilisé comme framework principal dans chaque service applicatif. Chaque service contient une structure Django classique avec :

- un fichier `manage.py` ;
- un dossier `config/` avec `settings.py`, `urls.py`, `asgi.py` et `wsgi.py` ;
- un ou plusieurs modules `apps/` contenant les vues, modèles, serializers, permissions, URLs et tests ;
- un `Dockerfile` ;
- un fichier `requirements.txt`.

Le projet utilise aussi **Django REST Framework** pour exposer des APIs JSON. Les endpoints REST sont utilisés pour faire communiquer les services entre eux et pour fournir les données à l’interface utilisateur.

Django apporte plusieurs avantages dans ce projet :

1. **Organisation claire du code** : chaque service possède ses apps Django, ses vues, ses serializers et ses URLs.
2. **ORM et migrations** : les services qui stockent des données relationnelles utilisent PostgreSQL avec les modèles Django et les migrations.
3. **Admin Django** : certains services exposent une interface admin utile pour gérer ou inspecter les données.
4. **Authentification JWT** : les services utilisent des tokens JWT partagés grâce à une clé commune.
5. **APIs REST** : les échanges entre services sont simples et se font via HTTP.

Le projet ne partage pas directement les modèles Django entre services. Par exemple, `order_service` ne fait pas de clé étrangère vers les tables de `product_service`. À la place, il appelle l’API du catalogue pour récupérer les informations nécessaires. Cela respecte le principe microservices : chaque service possède ses données et expose ce dont les autres services ont besoin via une API.

---

## 3. Vue globale de l’architecture microservices

L’architecture est lancée par Docker Compose. Le fichier `docker-compose.yml` définit les services applicatifs suivants :

| Service | Port local | Rôle principal |
|---|---:|---|
| `main_service` | 8000 | Gateway Django et pages HTML |
| `user_service` | 8001 | Authentification et profils |
| `product_service` | 8002 | Catalogue produits et images |
| `order_service` | 8003 | Commandes |
| `search_service` | 8004 | Recherche visuelle et indexation |
| `qdrant` | 6333 | Base vectorielle |
| `nginx` | 8080 | Reverse proxy public |

Chaque service Django a aussi sa propre base PostgreSQL :

- `postgres_main` pour `main_service` ;
- `postgres_users` pour `user_service` ;
- `postgres_products` pour `product_service` ;
- `postgres_orders` pour `order_service` ;
- `postgres_search` pour `search_service`.

Cette séparation montre que chaque microservice est responsable de son propre stockage. Les services ne se connectent pas directement à la base de données d’un autre service. Quand un service a besoin d’une information externe, il passe par une API HTTP.

La communication générale peut être résumée ainsi :

```text
Navigateur
   |
   v
Nginx : http://localhost:8080
   |
   v
main_service ou services API selon la route
   |
   +--> user_service pour auth/profile
   +--> product_service pour catalogue/images
   +--> order_service pour commandes
   +--> search_service pour recherche visuelle
              |
              v
           Qdrant
```

Nginx joue le rôle de porte d’entrée publique. Il reçoit les requêtes sur `localhost:8080` et les redirige vers les services internes. Par exemple, `/api/auth/` va vers `user_service`, `/api/products/` va vers `product_service`, `/api/orders/` va vers `order_service`, alors que `/api/search/`, `/api/gradcam/`, `/auth/`, `/static/` et `/` passent par `main_service`.

---

## 4. Le service principal : `main_service`

`main_service` est le service Django qui sert de gateway et d’interface utilisateur. Il expose les pages principales du site, les pages d’authentification, la page de démonstration et certains endpoints API qui coordonnent plusieurs services.

Il ne possède pas la logique métier complète du catalogue, des utilisateurs ou de la recherche. Son rôle est plutôt de recevoir les actions du navigateur, d’appeler le bon service interne, puis de renvoyer une réponse cohérente à l’utilisateur.

Dans `main_service/apps/core/views.py`, on trouve par exemple :

- `health()` : vérifie l’état de la base du service principal ;
- `SearchView` : reçoit une image envoyée par l’utilisateur, l’envoie au service de recherche, puis hydrate les résultats avec les informations du catalogue ;
- `ProductListView` et `ProductCategoryView` : proxys vers le catalogue ;
- `ProductImageUploadView` : transmet les uploads d’images au service produit ;
- `DemoPageView` : affiche une page de démonstration.

Le service contient aussi des proxys HTTP dans `main_service/apps/core/services/` :

- `catalog_proxy.py` pour parler à `product_service` ;
- `search_proxy.py` pour parler à `search_service` ;
- `search_hydration.py` pour transformer les résultats bruts de recherche en produits complets.

Un exemple important de flow dans `main_service` est la recherche par image :

1. L’utilisateur envoie une image depuis l’interface.
2. `main_service` reçoit l’image sur `/api/search/`.
3. Il envoie cette image à `search_service`.
4. `search_service` renvoie des IDs de produits avec des scores.
5. `main_service` appelle `product_service` avec ces IDs.
6. `product_service` renvoie les détails complets des produits.
7. `main_service` retourne au navigateur une liste de produits hydratés, triés par score.

Cette étape d’hydratation est importante : le moteur de recherche ne renvoie pas directement tout le produit, il renvoie surtout des identifiants et des scores. Le gateway complète ensuite les données avec le catalogue.

---

## 5. Le service utilisateur : `user_service`

`user_service` est le service responsable de l’authentification et des profils utilisateurs. Il utilise Django, Django REST Framework et SimpleJWT.

Son modèle principal est `UserProfile`, lié au modèle Django `User`. Ce profil ajoute un rôle utilisateur. Les rôles présents dans le projet sont :

- `admin` ;
- `seller` ;
- `client`.

Les serializers du service utilisateur gèrent :

- l’inscription ;
- le login ;
- le profil utilisateur ;
- l’ajout du rôle dans le token JWT.

Les routes principales exposées par ce service sont :

```text
/api/auth/register/
/api/auth/login/
/api/auth/profile/
```

Quand un utilisateur se connecte, `user_service` génère un token JWT. Ce token contient les informations nécessaires, dont le rôle. Les autres services peuvent ensuite lire ce rôle depuis le token pour autoriser ou refuser certaines actions.

Par exemple, un utilisateur `client` ne doit pas pouvoir créer un produit. Un `seller` peut créer des produits, et les permissions dans `product_service` vérifient ce rôle à partir du token. Cela évite de faire un appel à `user_service` à chaque requête protégée : le token transporte déjà les informations utiles.

Le flow d’authentification est le suivant :

1. Le navigateur envoie les identifiants à l’API d’authentification.
2. Nginx route `/api/auth/` vers `user_service`.
3. `user_service` vérifie les données utilisateur.
4. Il renvoie un token JWT.
5. Le frontend conserve ce token et l’utilise dans les appels suivants.
6. Les autres services vérifient le token avec la clé JWT partagée.

---

## 6. Le service produit : `product_service`

`product_service` est le service qui possède le catalogue. Il gère les catégories, les produits et les images associées aux produits.

Les modèles principaux sont :

- `Category` : nom et slug de catégorie ;
- `Product` : nom, description, prix, catégorie, vendeur et date de création ;
- `ProductImage` : fichier image, miniature en base64, indicateur d’image principale, état d’indexation et ID Qdrant.

Le service expose des APIs pour :

- créer et lister des catégories ;
- créer, lister, récupérer, modifier et supprimer des produits ;
- uploader des images de produits ;
- filtrer des produits par IDs, notamment pour l’hydratation des résultats de recherche.

Un point important de ce service est son lien avec `search_service`. Quand une image de produit est créée, les signaux Django déclenchent l’indexation de l’image dans le service de recherche. Le code dans `product_service/apps/products/signals.py` appelle la logique de cycle de vie située dans `lifecycle.py`, qui utilise ensuite `products/services/search_proxy.py` pour envoyer l’image à `search_service`.

Le flow d’upload et d’indexation est le suivant :

1. Un vendeur envoie une image produit.
2. `main_service` ou Nginx transmet la requête à `product_service`.
3. `product_service` sauvegarde le fichier dans le volume média partagé.
4. Le modèle `ProductImage` est créé.
5. Un signal Django déclenche l’indexation.
6. `product_service` envoie l’image à `search_service` via `/api/index/`.
7. `search_service` calcule un embedding et l’enregistre dans Qdrant.
8. `product_service` stocke l’ID Qdrant dans `ProductImage.qdrant_id`.

Le service produit contient aussi une commande `reindex_product_images`. Elle sert à reconstruire l’index de recherche à partir des images actuelles du catalogue. Cette commande est utile si Qdrant a été vidé, si le modèle de recherche change, ou si des IDs deviennent obsolètes.

---

## 7. Le service commande : `order_service`

`order_service` est responsable des commandes. Il possède sa propre base PostgreSQL et ne dépend pas directement des tables du catalogue.

Ses modèles principaux sont :

- `Order` : utilisateur, username, email, date de création ;
- `OrderItem` : ID produit, nom produit, catégorie, quantité, prix unitaire.

Le choix important ici est l’utilisation de **snapshots**. Quand une commande est créée, le service commande récupère les informations actuelles du produit depuis `product_service`, puis les copie dans ses propres tables. Cela permet de garder un historique correct même si le produit est modifié ou supprimé plus tard.

Le flow de création de commande est le suivant :

1. L’utilisateur authentifié envoie une commande.
2. `order_service` lit l’utilisateur depuis le token JWT.
3. Il récupère les produits nécessaires depuis `product_service` grâce à `/api/products/?ids=...`.
4. Il valide les données de commande.
5. Il crée une ligne `Order`.
6. Il crée les lignes `OrderItem` avec les snapshots des produits.
7. Il renvoie la commande créée.

Le service utilise `transaction.atomic` dans le serializer de création afin que la commande soit créée complètement ou pas du tout. Cela évite d’avoir une commande partiellement enregistrée.

Quand une commande est relue, `order_service` peut aussi hydrater certains détails depuis le catalogue. Mais si le catalogue ne répond pas ou si le produit n’existe plus, le service peut toujours retourner les données snapshot stockées au moment de l’achat.

---

## 8. Le service recherche : `search_service`

`search_service` est le service le plus spécialisé. Il contient la logique de recherche visuelle par image. Il utilise Django REST Framework pour exposer une API, mais sa responsabilité principale n’est pas de gérer des tables relationnelles classiques. Il communique surtout avec Qdrant pour stocker et rechercher des vecteurs.

Ses composants principaux sont dans `search_service/apps/search/services/` :

- `quality.py` : vérifie la qualité de l’image ;
- `preprocess.py` : prépare l’image avant embedding ;
- `model_registry.py` : décrit les modèles disponibles et les collections Qdrant associées ;
- `embedder.py` : charge les modèles et calcule les embeddings ;
- `qdrant.py` : crée les collections, insère, cherche et supprime des vecteurs ;
- `qdrant_policy.py` : gère les seuils et certains contrôles de distribution ;
- `visualization.py` : produit les overlays Grad-CAM quand c’est supporté.

Les APIs importantes sont :

```text
POST /api/index/
POST /api/search/
DELETE /api/index/<product_id>/
```

Le flow d’indexation est le suivant :

1. `product_service` envoie une image et un `product_id`.
2. `search_service` vérifie la qualité de l’image.
3. Il applique le preprocessing.
4. Il calcule un embedding avec le modèle configuré.
5. Il stocke ce vecteur dans Qdrant.
6. Il ajoute dans le payload Qdrant le `product_id`, le `product_image_id` et le nom du fichier.
7. Il renvoie l’ID Qdrant.

Le flow de recherche est le suivant :

1. `main_service` envoie une image de recherche.
2. `search_service` valide la qualité de l’image.
3. Il applique le preprocessing.
4. Il calcule l’embedding de l’image.
5. Il interroge Qdrant pour trouver les vecteurs similaires.
6. Il applique des seuils et des contrôles OOD pour éviter les résultats trop faibles.
7. Il renvoie des résultats bruts : `product_id`, `product_image_id`, `qdrant_id` et `score`.

Ce service ne renvoie pas directement les détails complets des produits. C’est volontaire : `search_service` ne possède pas le catalogue. Il renvoie seulement les identifiants nécessaires, puis `main_service` demande les détails à `product_service`.

---

## 9. Containerisation avec Docker Compose

Chaque service Django est placé dans son propre container. Dans `docker-compose.yml`, chaque service applicatif utilise son propre dossier comme contexte de build :

```text
./main_service
./user_service
./product_service
./order_service
./search_service
```

Chaque container lance les migrations Django au démarrage, puis démarre le serveur. Les services `main_service`, `user_service`, `product_service` et `order_service` utilisent `runserver` dans la configuration locale. `search_service` utilise Gunicorn avec un worker et plusieurs threads, car c’est le service qui charge les modèles de recherche et qui est plus lourd.

Les variables d’environnement définissent les connexions internes. Par exemple :

- `PRODUCT_SERVICE_URL=http://productservice:8002` ;
- `USER_SERVICE_URL=http://userservice:8001` ;
- `SEARCH_SERVICE_URL=http://searchservice:8004` ;
- `QDRANT_URL=http://qdrant:6333`.

Docker Compose donne aussi des alias réseau aux services :

- `mainservice` ;
- `userservice` ;
- `productservice` ;
- `orderservice` ;
- `searchservice`.

Ces alias permettent aux containers de communiquer par nom au lieu d’utiliser `localhost`. Dans Docker, `localhost` représenterait le container lui-même, donc les URLs internes utilisent les noms des services.

Les volumes sont aussi importants :

- chaque base PostgreSQL possède son volume dédié ;
- Qdrant possède `qdrant_data` ;
- les fichiers médias utilisent `media_data`.

Le volume `media_data` est partagé entre `product_service`, `main_service`, `search_service` et Nginx. Cela permet au catalogue d’écrire les images, au gateway de les lire, au moteur de recherche de les traiter, et à Nginx de les servir via `/media/`.

---

## 10. Communication entre services et circulation des données

La communication entre microservices se fait principalement par HTTP avec des APIs REST. Le projet utilise la bibliothèque standard `urllib` pour les appels internes au lieu d’un client externe comme `requests`.

### Authentification

```text
Navigateur -> user_service -> token JWT -> autres services
```

Le token JWT contient le rôle utilisateur. Les services peuvent ensuite autoriser ou refuser les actions sans appeler constamment `user_service`.

### Catalogue

```text
Navigateur/main_service -> product_service -> PostgreSQL products
```

Le catalogue est la source de vérité pour les produits. Les autres services ne lisent pas directement sa base, ils passent par son API.

### Recherche visuelle

```text
Image upload produit
   -> product_service
   -> search_service
   -> Qdrant

Image recherche utilisateur
   -> main_service
   -> search_service
   -> Qdrant
   -> main_service
   -> product_service
   -> réponse hydratée
```

La recherche est un bon exemple de séparation microservices. Qdrant contient des vecteurs et des IDs, mais pas les fiches produits complètes. Les produits restent dans `product_service`. Le `main_service` combine donc deux sources : les scores venant de `search_service` et les détails venant de `product_service`.

### Commandes

```text
Utilisateur -> order_service -> product_service -> PostgreSQL orders
```

Lors de la création d’une commande, `order_service` récupère les données produit puis les copie dans ses propres tables. Cela protège l’historique des commandes contre les modifications futures du catalogue.

---

## 11. Conclusion

Le projet utilise Django dans une architecture microservices locale et containerisée. Chaque domaine métier possède son service : utilisateurs, produits, commandes et recherche. Le `main_service` agit comme gateway et interface utilisateur, tandis que Nginx sert de reverse proxy public.

La séparation des bases PostgreSQL montre que chaque service possède ses données. Les communications passent par HTTP et par des APIs REST. Le token JWT permet de partager l’identité et le rôle utilisateur entre les services sans session centrale. Pour la recherche visuelle, `search_service` isole toute la logique ML et Qdrant, tandis que `product_service` garde la responsabilité du catalogue.

Cette architecture rend le projet plus clair : chaque service a une responsabilité précise, peut être lancé dans son propre container, possède sa propre configuration et communique avec les autres à travers une API définie. La circulation des données est donc contrôlée : les utilisateurs viennent de `user_service`, les produits de `product_service`, les commandes de `order_service`, les vecteurs de `search_service` et Qdrant, et `main_service` assemble ces informations pour l’expérience finale de l’utilisateur.
