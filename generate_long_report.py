from __future__ import annotations

import html
import subprocess
import textwrap
from pathlib import Path


ROOT = Path('/tmp/opencode/wams_report_long')
ASSETS = ROOT / 'assets'
ASSETS.mkdir(parents=True, exist_ok=True)


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding='utf-8')


def svg_file(name: str, content: str) -> None:
    path = ASSETS / f'{name}.svg'
    write(path, content)
    subprocess.run(['rsvg-convert', str(path), '-o', str(ASSETS / f'{name}.png')], check=True)


svg_file(
    'architecture',
    """<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='760' viewBox='0 0 1200 760'>
  <defs>
    <style>
      .box { fill:#ffffff; stroke:#2b4c7e; stroke-width:3; rx:18; ry:18; }
      .main { fill:#eef6ff; stroke:#0f6ab4; stroke-width:4; rx:18; ry:18; }
      .db { fill:#fff7ed; stroke:#c96a00; stroke-width:3; rx:18; ry:18; }
      .vector { fill:#f3e8ff; stroke:#8b5cf6; stroke-width:3; rx:18; ry:18; }
      .title { font: 700 28px Arial, sans-serif; fill:#10233f; }
      .label { font: 600 20px Arial, sans-serif; fill:#10233f; }
      .small { font: 400 16px Arial, sans-serif; fill:#334155; }
      .arrow { stroke:#334155; stroke-width:4; fill:none; marker-end:url(#m); }
    </style>
    <marker id='m' markerWidth='12' markerHeight='12' refX='10' refY='6' orient='auto'>
      <path d='M0,0 L12,6 L0,12 z' fill='#334155'/>
    </marker>
  </defs>
  <rect x='20' y='20' width='1160' height='720' fill='#f8fafc' stroke='#cbd5e1' rx='24'/>
  <text x='600' y='60' text-anchor='middle' class='title'>Architecture générale du projet</text>
  <rect x='430' y='100' width='340' height='80' class='box'/>
  <text x='600' y='145' text-anchor='middle' class='label'>Navigateur</text>
  <text x='600' y='168' text-anchor='middle' class='small'>utilisateur final</text>

  <rect x='430' y='210' width='340' height='90' class='main'/>
  <text x='600' y='248' text-anchor='middle' class='label'>Nginx</text>
  <text x='600' y='272' text-anchor='middle' class='small'>porte d'entrée publique</text>

  <rect x='100' y='360' width='180' height='80' class='box'/>
  <text x='190' y='405' text-anchor='middle' class='label'>main_service</text>
  <rect x='335' y='360' width='180' height='80' class='box'/>
  <text x='425' y='405' text-anchor='middle' class='label'>user_service</text>
  <rect x='570' y='360' width='180' height='80' class='box'/>
  <text x='660' y='405' text-anchor='middle' class='label'>product_service</text>
  <rect x='805' y='360' width='180' height='80' class='box'/>
  <text x='895' y='405' text-anchor='middle' class='label'>order_service</text>
  <rect x='1040' y='360' width='120' height='80' class='box'/>
  <text x='1100' y='397' text-anchor='middle' class='label'>search</text>
  <text x='1100' y='419' text-anchor='middle' class='small'>service</text>

  <rect x='120' y='560' width='150' height='75' class='db'/>
  <text x='195' y='603' text-anchor='middle' class='small'>Postgres main</text>
  <rect x='355' y='560' width='150' height='75' class='db'/>
  <text x='430' y='603' text-anchor='middle' class='small'>Postgres users</text>
  <rect x='590' y='560' width='150' height='75' class='db'/>
  <text x='665' y='603' text-anchor='middle' class='small'>Postgres products</text>
  <rect x='825' y='560' width='150' height='75' class='db'/>
  <text x='900' y='603' text-anchor='middle' class='small'>Postgres orders</text>
  <rect x='1060' y='560' width='100' height='75' class='vector'/>
  <text x='1110' y='603' text-anchor='middle' class='small'>Qdrant</text>

  <path d='M600 180 L600 210' class='arrow'/>
  <path d='M600 300 L190 360' class='arrow'/>
  <path d='M600 300 L425 360' class='arrow'/>
  <path d='M600 300 L660 360' class='arrow'/>
  <path d='M600 300 L895 360' class='arrow'/>
  <path d='M600 300 L1100 360' class='arrow'/>
  <path d='M190 440 L195 560' class='arrow'/>
  <path d='M425 440 L430 560' class='arrow'/>
  <path d='M660 440 L665 560' class='arrow'/>
  <path d='M895 440 L900 560' class='arrow'/>
  <path d='M1100 440 L1110 560' class='arrow'/>

  <text x='610' y='470' text-anchor='middle' class='small'>HTTP REST entre services</text>
  <text x='610' y='495' text-anchor='middle' class='small'>bases séparées par domaine métier</text>
</svg>""",
)

svg_file(
    'auth_flow',
    """<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='520' viewBox='0 0 1200 520'>
  <defs>
    <style>
      .box { fill:#ffffff; stroke:#1d4ed8; stroke-width:3; rx:16; ry:16; }
      .token { fill:#dcfce7; stroke:#16a34a; stroke-width:3; rx:16; ry:16; }
      .title { font: 700 28px Arial, sans-serif; fill:#10233f; }
      .label { font: 600 20px Arial, sans-serif; fill:#10233f; }
      .small { font: 400 16px Arial, sans-serif; fill:#334155; }
      .arrow { stroke:#334155; stroke-width:4; fill:none; marker-end:url(#m); }
    </style>
    <marker id='m' markerWidth='12' markerHeight='12' refX='10' refY='6' orient='auto'><path d='M0,0 L12,6 L0,12 z' fill='#334155'/></marker>
  </defs>
  <rect x='20' y='20' width='1160' height='480' fill='#f8fafc' stroke='#cbd5e1' rx='24'/>
  <text x='600' y='60' text-anchor='middle' class='title'>Flux d'authentification JWT</text>
  <rect x='70' y='180' width='180' height='80' class='box'/>
  <text x='160' y='225' text-anchor='middle' class='label'>Navigateur</text>
  <rect x='310' y='180' width='200' height='80' class='box'/>
  <text x='410' y='218' text-anchor='middle' class='label'>main_service</text>
  <text x='410' y='242' text-anchor='middle' class='small'>page / formulaire</text>
  <rect x='560' y='180' width='200' height='80' class='box'/>
  <text x='660' y='218' text-anchor='middle' class='label'>user_service</text>
  <text x='660' y='242' text-anchor='middle' class='small'>login / register</text>
  <rect x='820' y='160' width='320' height='120' class='token'/>
  <text x='980' y='205' text-anchor='middle' class='label'>JWT</text>
  <text x='980' y='232' text-anchor='middle' class='small'>role + username + signature</text>
  <path d='M250 220 L310 220' class='arrow'/>
  <path d='M510 220 L560 220' class='arrow'/>
  <path d='M760 220 L820 220' class='arrow'/>
  <path d='M980 280 L980 360' class='arrow'/>
  <rect x='360' y='350' width='480' height='80' class='box'/>
  <text x='600' y='388' text-anchor='middle' class='label'>autres services</text>
  <text x='600' y='412' text-anchor='middle' class='small'>vérifient le token sans session centrale</text>
  <path d='M980 280 L600 350' class='arrow'/>
</svg>""",
)

svg_file(
    'search_flow',
    """<svg xmlns='http://www.w3.org/2000/svg' width='1250' height='620' viewBox='0 0 1250 620'>
  <defs>
    <style>
      .box { fill:#ffffff; stroke:#7c3aed; stroke-width:3; rx:16; ry:16; }
      .main { fill:#eef2ff; stroke:#4f46e5; stroke-width:4; rx:16; ry:16; }
      .db { fill:#faf5ff; stroke:#9333ea; stroke-width:3; rx:16; ry:16; }
      .title { font: 700 28px Arial, sans-serif; fill:#10233f; }
      .label { font: 600 20px Arial, sans-serif; fill:#10233f; }
      .small { font: 400 16px Arial, sans-serif; fill:#334155; }
      .arrow { stroke:#334155; stroke-width:4; fill:none; marker-end:url(#m); }
    </style>
    <marker id='m' markerWidth='12' markerHeight='12' refX='10' refY='6' orient='auto'><path d='M0,0 L12,6 L0,12 z' fill='#334155'/></marker>
  </defs>
  <rect x='20' y='20' width='1210' height='580' fill='#f8fafc' stroke='#cbd5e1' rx='24'/>
  <text x='625' y='60' text-anchor='middle' class='title'>Recherche visuelle et hydratation des résultats</text>
  <rect x='60' y='150' width='180' height='80' class='box'/>
  <text x='150' y='195' text-anchor='middle' class='label'>Image utilisateur</text>
  <rect x='290' y='140' width='210' height='100' class='main'/>
  <text x='395' y='184' text-anchor='middle' class='label'>main_service</text>
  <text x='395' y='210' text-anchor='middle' class='small'>coordination</text>
  <rect x='560' y='140' width='220' height='100' class='box'/>
  <text x='670' y='184' text-anchor='middle' class='label'>search_service</text>
  <text x='670' y='210' text-anchor='middle' class='small'>embedding + Qdrant</text>
  <rect x='840' y='140' width='180' height='100' class='db'/>
  <text x='930' y='184' text-anchor='middle' class='label'>Qdrant</text>
  <text x='930' y='210' text-anchor='middle' class='small'>vecteurs + scores</text>
  <rect x='1050' y='140' width='160' height='100' class='box'/>
  <text x='1130' y='184' text-anchor='middle' class='label'>product_service</text>
  <text x='1130' y='210' text-anchor='middle' class='small'>détails produits</text>
  <path d='M240 190 L290 190' class='arrow'/>
  <path d='M500 190 L560 190' class='arrow'/>
  <path d='M780 190 L840 190' class='arrow'/>
  <path d='M1020 190 L1050 190' class='arrow'/>
  <rect x='250' y='380' width='760' height='120' class='main'/>
  <text x='630' y='430' text-anchor='middle' class='label'>réponse finale</text>
  <text x='630' y='458' text-anchor='middle' class='small'>matches hydratés avec images, prix, catégories et score</text>
  <path d='M1130 240 L630 380' class='arrow'/>
</svg>""",
)

svg_file(
    'order_flow',
    """<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='560' viewBox='0 0 1200 560'>
  <defs>
    <style>
      .box { fill:#ffffff; stroke:#ea580c; stroke-width:3; rx:16; ry:16; }
      .main { fill:#fff7ed; stroke:#f97316; stroke-width:4; rx:16; ry:16; }
      .db { fill:#fef2f2; stroke:#ef4444; stroke-width:3; rx:16; ry:16; }
      .title { font: 700 28px Arial, sans-serif; fill:#10233f; }
      .label { font: 600 20px Arial, sans-serif; fill:#10233f; }
      .small { font: 400 16px Arial, sans-serif; fill:#334155; }
      .arrow { stroke:#334155; stroke-width:4; fill:none; marker-end:url(#m); }
    </style>
    <marker id='m' markerWidth='12' markerHeight='12' refX='10' refY='6' orient='auto'><path d='M0,0 L12,6 L0,12 z' fill='#334155'/></marker>
  </defs>
  <rect x='20' y='20' width='1160' height='520' fill='#f8fafc' stroke='#cbd5e1' rx='24'/>
  <text x='600' y='60' text-anchor='middle' class='title'>Création d'une commande avec snapshots</text>
  <rect x='50' y='180' width='180' height='80' class='box'/>
  <text x='140' y='225' text-anchor='middle' class='label'>Client connecté</text>
  <rect x='280' y='170' width='220' height='100' class='main'/>
  <text x='390' y='214' text-anchor='middle' class='label'>order_service</text>
  <text x='390' y='240' text-anchor='middle' class='small'>transaction atomique</text>
  <rect x='560' y='170' width='220' height='100' class='box'/>
  <text x='670' y='214' text-anchor='middle' class='label'>product_service</text>
  <text x='670' y='240' text-anchor='middle' class='small'>infos produits actuelles</text>
  <rect x='860' y='170' width='280' height='100' class='db'/>
  <text x='1000' y='214' text-anchor='middle' class='label'>Postgres orders</text>
  <text x='1000' y='240' text-anchor='middle' class='small'>Order + OrderItem snapshot</text>
  <path d='M230 220 L280 220' class='arrow'/>
  <path d='M500 220 L560 220' class='arrow'/>
  <path d='M780 220 L860 220' class='arrow'/>
  <path d='M390 270 L390 360' class='arrow'/>
  <rect x='300' y='360' width='500' height='100' class='main'/>
  <text x='550' y='405' text-anchor='middle' class='label'>résultat</text>
  <text x='550' y='432' text-anchor='middle' class='small'>la commande reste lisible même si le catalogue change</text>
</svg>""",
)

svg_file(
    'docker_stack',
    """<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='640' viewBox='0 0 1200 640'>
  <defs>
    <style>
      .box { fill:#ffffff; stroke:#0f766e; stroke-width:3; rx:16; ry:16; }
      .stack { fill:#ecfeff; stroke:#06b6d4; stroke-width:4; rx:20; ry:20; }
      .db { fill:#f0fdf4; stroke:#16a34a; stroke-width:3; rx:16; ry:16; }
      .title { font: 700 28px Arial, sans-serif; fill:#10233f; }
      .label { font: 600 18px Arial, sans-serif; fill:#10233f; }
      .small { font: 400 15px Arial, sans-serif; fill:#334155; }
      .arrow { stroke:#334155; stroke-width:3; fill:none; marker-end:url(#m); }
    </style>
    <marker id='m' markerWidth='12' markerHeight='12' refX='10' refY='6' orient='auto'><path d='M0,0 L12,6 L0,12 z' fill='#334155'/></marker>
  </defs>
  <rect x='20' y='20' width='1160' height='600' fill='#f8fafc' stroke='#cbd5e1' rx='24'/>
  <text x='600' y='60' text-anchor='middle' class='title'>Déploiement Docker Compose</text>
  <rect x='80' y='120' width='1040' height='160' class='stack'/>
  <text x='600' y='155' text-anchor='middle' class='label'>Conteneurs applicatifs</text>
  <text x='600' y='182' text-anchor='middle' class='small'>main_service - user_service - product_service - order_service - search_service - nginx</text>
  <text x='600' y='208' text-anchor='middle' class='small'>chaque service a son propre Dockerfile et ses propres variables d'environnement</text>
  <text x='600' y='236' text-anchor='middle' class='small'>les services Django démarrent après migration, puis écoutent chacun sur son port</text>
  <rect x='90' y='350' width='170' height='90' class='db'/>
  <text x='175' y='393' text-anchor='middle' class='label'>Postgres main</text>
  <rect x='290' y='350' width='170' height='90' class='db'/>
  <text x='375' y='393' text-anchor='middle' class='label'>Postgres users</text>
  <rect x='490' y='350' width='170' height='90' class='db'/>
  <text x='575' y='393' text-anchor='middle' class='label'>Postgres products</text>
  <rect x='690' y='350' width='170' height='90' class='db'/>
  <text x='775' y='393' text-anchor='middle' class='label'>Postgres orders</text>
  <rect x='890' y='350' width='170' height='90' class='db'/>
  <text x='975' y='393' text-anchor='middle' class='label'>Postgres search</text>
  <rect x='1040' y='470' width='100' height='70' class='box'/>
  <text x='1090' y='512' text-anchor='middle' class='label'>Qdrant</text>
  <path d='M175 440 L175 470' class='arrow'/>
  <path d='M375 440 L375 470' class='arrow'/>
  <path d='M575 440 L575 470' class='arrow'/>
  <path d='M775 440 L775 470' class='arrow'/>
  <path d='M975 440 L975 470' class='arrow'/>
  <text x='600' y='575' text-anchor='middle' class='small'>les volumes gardent les données, les images et les vecteurs</text>
</svg>""",
)


def p(text: str) -> str:
    return f'<p>{html.escape(text)}</p>'


def h1(text: str) -> str:
    return f'<h1>{html.escape(text)}</h1>'


def h2(text: str) -> str:
    return f'<h2>{html.escape(text)}</h2>'


def code(text: str) -> str:
    return f'<pre>{html.escape(textwrap.dedent(text).strip())}</pre>'


sections: list[str] = []
sections.append(
    '''<div class="title-page">
  <h1>Rapport de projet</h1>
  <h2>Analyse détaillée du projet WAMS / Apex Motors</h2>
  <p class="center">Version longue en français simple<br>Année universitaire 2025 / 2026</p>
  <table class="meta">
    <tr><td>Projet</td><td>Apex Motors</td></tr>
    <tr><td>Nature</td><td>Plateforme e-commerce en microservices Django</td></tr>
    <tr><td>Base d'analyse</td><td>Code source, scripts de déploiement et rapports PDF de référence</td></tr>
    <tr><td>Objectif</td><td>Expliquer clairement l'architecture, les API, les choix techniques et le fonctionnement global</td></tr>
  </table>
</div>
<div class="page-break"></div>'''
)

sections.append(h1('Résumé') + p("Ce rapport décrit le projet Apex Motors de façon détaillée. Le système est organisé en plusieurs services Django séparés. Chacun a un rôle précis : authentification, catalogue, commandes, recherche visuelle et passerelle principale. Le but est de garder le code lisible, de faciliter le déploiement local et de montrer une vraie séparation entre la logique métier et la partie intelligence artificielle.") + p("Le projet est aussi intéressant parce qu'il ne se limite pas à un CRUD classique. Il ajoute une recherche par image avec embeddings et Qdrant, des règles de permission basées sur le rôle utilisateur, des commandes avec snapshots, et une orchestration complète avec Docker Compose et Nginx.") + '<div class="page-break"></div>')

sections.append(h1('Table des matières') + '<ul>' + ''.join(f'<li>{html.escape(x)}</li>' for x in [
    '1. Introduction et contexte', '2. Méthode d’analyse', '3. Vue globale de l’architecture', '4. Service d’authentification', '5. Service catalogue', '6. Service commandes', '7. Service recherche', '8. Communication entre APIs', '9. Sécurité et permissions', '10. Déploiement Docker', '11. Parcours utilisateur', '12. Extraits de code', '13. Tests et validation', '14. Bilan du travail', '15. Conclusion et perspectives']) + '</ul>' + '<div class="page-break"></div>')

sections.append(h1('1. Introduction et contexte') + p("Apex Motors est une application e-commerce de démonstration centrée sur les voitures et les produits liés à l'automobile. Le projet montre comment construire une plateforme plus réaliste qu'un simple monolithe. L'application est découpée en plusieurs services indépendants pour éviter que tout le code soit mélangé dans un seul endroit.") + p("Cette approche a un intérêt pédagogique fort. On voit comment séparer les responsabilités, comment faire communiquer plusieurs API REST, comment gérer des bases de données distinctes, et comment intégrer une brique de recherche intelligente sans alourdir le reste du système.") + p("Dans les documents de référence du dépôt, le même esprit apparaît : on retrouve une architecture distribuée, des services clairement nommés, un proxy public, des bases séparées et des parcours utilisateurs bien définis. Le projet va donc au-delà d'un simple site web : il ressemble à un mini-système de production.") + '<img src="assets/architecture.png" class="diagram" alt="architecture"/>' + '<div class="page-break"></div>')

sections.append(h1('2. Méthode d’analyse') + p("Pour préparer ce rapport, j'ai d'abord parcouru la structure du dépôt afin de comprendre les services présents et leurs responsabilités. J'ai ensuite lu les fichiers de configuration, les vues, les serializers, les permissions, les modèles et les scripts de déploiement. J'ai aussi extrait le contenu de deux rapports PDF de référence pour m'inspirer du style académique et de l'organisation des chapitres.") + p("Cette manière de travailler permet de rester proche du code réel. Le rapport ne décrit pas une architecture imaginée : il suit ce qui est effectivement implémenté dans le dépôt. Cela évite les généralités et permet d'expliquer le rôle de chaque fichier utile.") + p("J'ai surtout cherché quatre choses : comment le système s'initialise, comment les services échangent des données, comment les rôles utilisateur sont appliqués, et comment la recherche visuelle est construite de bout en bout.") + '<div class="page-break"></div>')

sections.append(h1('3. Vue globale de l’architecture') + p("Le dépôt utilise cinq services applicatifs principaux : main_service, user_service, product_service, order_service et search_service. Chaque service a sa propre base PostgreSQL. En plus de cela, Qdrant stocke les vecteurs d'images et Nginx sert de point d'entrée public.") + p("Le choix de plusieurs bases séparées est important. Il évite les dépendances directes entre les tables des différents domaines. Par exemple, order_service ne lit pas directement les tables du catalogue. Il interroge product_service via HTTP, puis stocke ses propres snapshots.") + p("Cette séparation rend le projet plus clair. On sait exactement où se trouve chaque responsabilité. Les données utilisateurs restent dans user_service, les produits dans product_service, les commandes dans order_service, et la recherche vectorielle dans search_service + Qdrant.") + '<img src="assets/docker_stack.png" class="diagram" alt="docker stack"/>' + '<div class="page-break"></div>')

sections.append(h1('4. Service d’authentification') + p("user_service est le service responsable des comptes. Son rôle est simple mais central : créer les utilisateurs, gérer les profils et produire des tokens JWT. Le modèle UserProfile ajoute un champ role avec trois valeurs : admin, seller et client.") + p("Le token JWT est enrichi avec le rôle et le nom d'utilisateur. C'est un choix pratique, car les autres services peuvent vérifier les droits sans appeler user_service à chaque requête. On garde ainsi une authentification stateless, plus adaptée à un système distribué.") + h2('Routes principales') + '<table class="api-table"><tr><th>Route</th><th>Méthode</th><th>Rôle</th></tr><tr><td>/api/auth/register/</td><td>POST</td><td>Créer un compte</td></tr><tr><td>/api/auth/login/</td><td>POST</td><td>Obtenir un token</td></tr><tr><td>/api/auth/profile/</td><td>GET</td><td>Lire le profil</td></tr></table>' + p("Le code de sérialisation ajoute aussi le rôle dans la réponse de connexion. Cela simplifie le front et évite de multiplier les appels. Dans la logique du projet, le rôle n'est pas un détail : il détermine qui peut créer des produits, qui peut modifier le catalogue et qui peut passer une commande.") + '<img src="assets/auth_flow.png" class="diagram" alt="auth flow"/>' + '<div class="page-break"></div>')

sections.append(h1('5. Service catalogue') + p("product_service est le cœur métier du catalogue. Il gère les catégories, les produits et les images associées. Le modèle Product contient le nom, la description, le prix, la catégorie, le vendeur et la date de création. Le modèle ProductImage conserve l'image, une miniature base64, un indicateur d'image principale, l'état d'indexation et l'identifiant Qdrant.") + p("Un détail intéressant est la génération de miniature dans le modèle. Le fichier image est ouvert, corrigé si nécessaire, redimensionné, compressé et converti en base64. Cela permet d'avoir un aperçu rapide sans charger tout le fichier dans l'interface.") + p("Le service applique aussi des permissions métier. Un seller peut écrire dans le catalogue, mais un client ne le peut pas. En plus, un produit peut être modifié seulement par son propriétaire vendeur. C'est une règle simple, mais importante pour maintenir la cohérence des données.") + code("""class ProductSerializer(serializers.ModelSerializer):
    images = ProductImageSerializer(many=True, read_only=True)
    image_files = serializers.ListField(child=serializers.ImageField(), write_only=True, required=False)

    def validate(self, attrs):
        image_files = attrs.get("image_files") or []
        if self.instance is None and len(image_files) < 5:
            raise serializers.ValidationError({"image_files": "Provide at least 5 images when creating a product."})
        return attrs""") + p("Cette validation montre une règle métier claire : la création d'un produit demande au moins cinq images. Le but est d'améliorer la recherche visuelle et d'avoir un catalogue plus riche.") + '<div class="page-break"></div>')

sections.append(h1('6. Service commandes') + p("order_service gère les commandes de manière indépendante. Il enregistre l'utilisateur, la date, puis les lignes de commande avec des snapshots complets du produit. Cette méthode protège l'historique si le produit est modifié ou supprimé plus tard.") + p("Le service utilise une transaction atomique. Cela veut dire que la commande entière est créée ou bien elle échoue complètement. C'est un point essentiel pour éviter les commandes partiellement enregistrées.") + p("Au moment de la création, le service récupère les produits nécessaires depuis product_service. Il ne copie pas seulement l'identifiant produit, mais aussi le nom, la description, la catégorie et le prix unitaire. Le résultat est plus stable et plus lisible pour l'utilisateur final.") + h2('Route principale') + '<table class="api-table"><tr><th>Route</th><th>Méthode</th><th>Rôle</th></tr><tr><td>/api/orders/</td><td>GET / POST</td><td>Lister ou créer une commande</td></tr><tr><td>/api/orders/&lt;id&gt;/</td><td>GET</td><td>Lire une commande précise</td></tr></table>' + '<img src="assets/order_flow.png" class="diagram" alt="order flow"/>' + '<div class="page-break"></div>')

sections.append(h1('7. Service recherche') + p("search_service est la partie la plus technique du projet. Il reçoit des images, les vérifie, les prépare, calcule des embeddings et interroge Qdrant pour retrouver des produits similaires. C'est la brique qui donne au projet son aspect intelligent.") + p("Le pipeline est découpé en étapes simples : contrôle qualité de l'image, preprocessing, embedding, recherche vectorielle, filtrage et réponse finale. Cette découpe rend le code plus facile à suivre et plus facile à modifier si le modèle change.") + p("Le service ne renvoie pas les fiches produits complètes. Il renvoie surtout des identifiants, des scores et des métadonnées. Ensuite, main_service récupère les détails du catalogue et reconstruit la réponse finale pour l'interface.") + h2('API recherche') + '<table class="api-table"><tr><th>Route</th><th>Méthode</th><th>Rôle</th></tr><tr><td>/api/index/</td><td>POST</td><td>Indexer une image produit</td></tr><tr><td>/api/search/</td><td>POST</td><td>Rechercher une image similaire</td></tr><tr><td>/api/index/&lt;product_id&gt;/</td><td>DELETE</td><td>Supprimer les vecteurs d'un produit</td></tr></table>' + code("""def search_image(*, image_bytes: bytes, limit: int = 10, score_threshold: float | None = None, model_id: str | None = None):
    ok, reason = validate_image_quality(image_bytes)
    if not ok:
        return UseCaseResponse({"detail": reason}, status.HTTP_400_BAD_REQUEST)

    embedding_bytes = preprocess_image_bytes(image_bytes)
    vector = get_embedder(model_id).embed(embedding_bytes)
    results = search_vectors(vector=vector, limit=limit, score_threshold=score_threshold, model_id=model_id)
    matches = _shape_matches(_filter_results(results, thresholds["min_score"]))
    return UseCaseResponse({"matches": matches}, status.HTTP_200_OK)""") + p("Ce morceau illustre bien la logique générale. Le code reste compact, mais il couvre la chaîne complète de recherche, de l'entrée image jusqu'au résultat exploitable.") + '<img src="assets/search_flow.png" class="diagram" alt="search flow"/>' + '<div class="page-break"></div>')

sections.append(h1('8. Communication entre APIs') + p("La communication entre services se fait presque toujours par HTTP et par APIs REST. Le projet évite de partager directement des modèles Django entre services. C'est une bonne pratique dans une architecture microservices, car chaque domaine reste indépendant.") + p("main_service joue un rôle de passerelle. Le navigateur parle surtout à lui, puis il contacte user_service, product_service, order_service ou search_service selon l'action demandée. Cela donne une seule porte d'entrée côté interface.") + p("Quand une image est envoyée pour la recherche, main_service appelle search_service, puis récupère les produits par leurs identifiants via product_service. Ce mécanisme d'hydratation est important : il transforme une réponse technique, centrée sur les vecteurs, en réponse métier lisible.") + p("Le même principe existe pour les commandes. order_service interroge product_service pour obtenir des données fraîches, puis les copie dans ses propres tables. Ici encore, l'API sert de frontière entre les domaines.") + h2('Résumé des échanges') + '<table class="api-table"><tr><th>Flux</th><th>Source</th><th>Cible</th><th>Résultat</th></tr><tr><td>Authentification</td><td>Navigateur</td><td>user_service</td><td>JWT avec rôle</td></tr><tr><td>Recherche image</td><td>main_service</td><td>search_service + product_service</td><td>Résultats hydratés</td></tr><tr><td>Ajout d'image</td><td>product_service</td><td>search_service + Qdrant</td><td>Indexation vectorielle</td></tr><tr><td>Commande</td><td>order_service</td><td>product_service</td><td>Snapshot de commande</td></tr></table>' + '<div class="page-break"></div>')

sections.append(h1('9. Sécurité et permissions') + p("Le projet applique une sécurité simple mais utile. Les rôles sont transmis dans le JWT. Les services utilisent ensuite ce rôle pour autoriser ou refuser certaines actions. Cela évite de réécrire la logique d'accès dans chaque service.") + p("Dans product_service, les droits d'écriture sont réservés aux vendeurs. Dans order_service, seuls les clients peuvent passer une commande. Cette règle est cohérente avec l'utilisation attendue de la plateforme.") + p("Les permissions sont pensées pour être lisibles. Le code ne cherche pas à faire une sécurité trop compliquée. Il s'agit plutôt d'une sécurité suffisante pour un projet académique ou de démonstration, avec une base propre pour aller plus loin si besoin.") + code("""class SellerWritePermission(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return _is_seller(request)

class ProductOwnerPermission(BasePermission):
    def has_object_permission(self, request, view, obj):
        return _is_seller(request) and obj.seller_username == _username(request)""") + p("Ces classes montrent une logique claire : lire est autorisé plus largement, écrire est contrôlé, et la propriété du produit est vérifiée au niveau objet.") + '<div class="page-break"></div>')

sections.append(h1('10. Déploiement Docker') + p("Le déploiement local repose sur Docker Compose. Chaque service a son image, son port, ses variables d'environnement et son volume si nécessaire. Le compose démarre aussi les bases PostgreSQL, Qdrant et Nginx.") + p("L'intérêt de cette structure est de pouvoir lancer tout le système avec une seule commande. Le projet devient alors facile à tester, à démontrer et à redémarrer proprement.") + p("Les noms réseau internes sont importants. Dans les conteneurs, localhost ne désigne pas la machine hôte, mais le conteneur lui-même. Le compose utilise donc des alias réseau comme userservice, productservice, orderservice et searchservice.") + p("Les volumes gardent les données, les images et les vecteurs. On sépare aussi les bases pour que chaque service conserve son autonomie.") + code("""main_service:
    ports:
      - "8000:8000"
  environment:
    PRODUCT_SERVICE_URL: http://productservice:8002
    SEARCH_SERVICE_URL: http://searchservice:8004

search_service:
  environment:
    QDRANT_URL: http://qdrant:6333
    DEFAULT_SEARCH_MODEL: dinov2_base_triplet_finetuned""") + p("Ce petit extrait résume l'idée du déploiement : des services indépendants, mais reliés par des URL internes stables.") + '<img src="assets/docker_stack.png" class="diagram" alt="docker stack"/>' + '<div class="page-break"></div>')

sections.append(h1('11. Parcours utilisateur') + p("Le parcours principal démarre par la page publique servie par Nginx puis par main_service. L'utilisateur peut se connecter, parcourir le catalogue, consulter les détails d'un produit, uploader des images en tant que vendeur et lancer une recherche visuelle.") + p("Le frontend est volontairement simple. Il n'y a pas une grosse application SPA séparée. Le projet garde une logique Django classique, avec des templates et un peu de JavaScript. Cela colle bien à l'objectif de démonstration.") + p("Le parcours vendeur est un peu plus riche. Il peut créer des produits avec plusieurs images, ce qui alimente ensuite la recherche visuelle. Le parcours client, lui, se concentre sur la découverte des produits et la commande.") + p("Ce découpage permet de montrer deux rôles différents dans la même plateforme, avec des droits différents et des interfaces adaptées.") + '<img src="assets/auth_flow.png" class="diagram" alt="auth flow"/>' + '<div class="page-break"></div>')

sections.append(h1('12. Extraits de code importants') + p("Les extraits ci-dessous résument le cœur du projet sans noyer le lecteur dans trop de code. Ils montrent les décisions techniques les plus utiles.") + code("""class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=16, choices=UserRole.choices, default=UserRole.CLIENT)""") + p("Ici, le profil utilisateur ajoute juste ce qu'il faut : un rôle métier simple.") + code("""@receiver(post_save, sender=ProductImage)
def auto_index_product_image(sender, instance: ProductImage, created: bool, **kwargs):
    if not created or not instance.image:
        return
    index_product_image_record(instance)""") + p("Ici, l'indexation part dès qu'une image produit est enregistrée.") + code("""@lru_cache(maxsize=None)
def get_embedder(model_id: str | None = None) -> BaseImageEmbedder:
    spec = get_model_spec(model_id)
    if spec.family == "dinov2":
        return DINOv2Embedder(spec.model_id)
    if spec.family == "clip":
        return CLIPImageEmbedder(spec.model_id)""") + p("Ici, le bon modèle d'embedding est choisi automatiquement selon la configuration.") + code("""@transaction.atomic
def create(self, validated_data):
    order = Order.objects.create(...)
    for item_data in items_data:
        OrderItem.objects.create(
            order=order,
            product_name=product["name"],
            unit_price=Decimal(str(product["price"])),
        )""") + p("Ici, les snapshots de commande sont écrits dans une transaction unique.") + '<div class="page-break"></div>')

sections.append(h1('13. Tests et validation') + p("Le dépôt contient des tests et des commandes de vérification qui montrent que le projet a été pensé pour être exécuté localement. La présence de routes de santé, de vues admin d'opérations et de scripts de seed facilite la validation du fonctionnement complet.") + p("Le fichier run-demo.md indique clairement la séquence à suivre : copier l'environnement, lancer Docker Compose, puis exécuter les commandes de seed. Cela réduit les erreurs de mise en route et donne un chemin simple pour la démonstration.") + p("Les points sensibles sont bien identifiés : Qdrant doit tourner pour la recherche, les bases PostgreSQL doivent être disponibles, et les images doivent être correctement indexées avant de lancer une recherche pertinente.") + p("Dans la pratique, ce type d'architecture se valide surtout par parcours complet : login, catalogue, upload d'image, indexation, recherche, puis création de commande. C'est exactement ce que le projet met en place.") + '<div class="page-break"></div>')

sections.append(h1('14. Bilan du travail') + p("Le projet est cohérent et bien découpé. Chaque service a une responsabilité principale, les API sont simples à comprendre, et la logique de recherche visuelle est isolée du reste. Cela rend le code plus propre et plus facile à maintenir.") + p("Les choix techniques sont adaptés au but du projet : Django pour la structure, DRF pour les API, JWT pour l'authentification, PostgreSQL pour les données métier, Qdrant pour les vecteurs, et Docker Compose pour l'exécution locale. Rien n'est ajouté gratuitement ; chaque outil a un rôle clair.") + p("Le résultat final est aussi intéressant sur le plan pédagogique. On voit comment un vrai système peut être découpé en services plus petits, comment les données circulent, et comment une partie IA peut vivre à côté d'un site e-commerce classique.") + '<div class="page-break"></div>')

sections.append(h1('15. Conclusion et perspectives') + p("En conclusion, Apex Motors est un bon exemple de projet microservices complet mais compréhensible. La solution montre une séparation nette des responsabilités, une sécurité simple, un mécanisme de recherche vectorielle, et un déploiement local bien organisé.") + p("Si le projet devait évoluer, on pourrait ajouter un meilleur monitoring, des tests d'intégration plus poussés, une documentation API plus formelle et peut-être une interface front plus riche. Mais la base actuelle est déjà solide pour une démonstration académique.") + p("Ce rapport plus long décrit l'ensemble du système, pas seulement un morceau. Il explique ce que fait chaque service, comment ils communiquent, pourquoi certaines décisions ont été prises, et comment l'utilisateur final en profite."))


html_template = """<!doctype html>
<html lang='fr'>
<head>
<meta charset='utf-8'>
<title>Rapport de projet Apex Motors</title>
<style>
  body {{ font-family: Arial, sans-serif; font-size: 11pt; line-height: 1.38; color: #111; }}
  h1 {{ font-size: 18pt; margin-top: 22px; margin-bottom: 10px; }}
  h2 {{ font-size: 13.5pt; margin-top: 16px; margin-bottom: 8px; }}
  .title-page {{ margin-top: 90px; text-align: center; }}
  .title-page h1 {{ font-size: 22pt; margin-bottom: 6px; }}
  .title-page h2 {{ font-size: 16pt; margin-top: 0; }}
  .center {{ text-align: center; }}
  .meta {{ width: 100%; border-collapse: collapse; margin-top: 28px; }}
  .meta td {{ border: 1px solid #999; padding: 9px; }}
  .meta td:first-child {{ background: #ededed; width: 30%; font-weight: bold; }}
  .api-table {{ width: 100%; border-collapse: collapse; margin: 10px 0 12px 0; }}
  .api-table th, .api-table td {{ border: 1px solid #999; padding: 7px; vertical-align: top; }}
  .api-table th {{ background: #d9eaf7; }}
  pre {{ background: #f3f4f6; border: 1px solid #999; padding: 10px; white-space: pre-wrap; font-family: 'Courier New', monospace; font-size: 9.2pt; }}
  .diagram {{ width: 100%; max-width: 1000px; display: block; margin: 12px auto; border: 1px solid #d1d5db; }}
  .page-break {{ page-break-after: always; }}
  ul {{ margin-top: 6px; }}
</style>
</head>
<body>
{content}
</body>
</html>"""


write(ROOT / 'report.html', html_template.format(content=''.join(sections)))
subprocess.run(['libreoffice', '--headless', '--convert-to', 'odt', '--outdir', str(ROOT), str(ROOT / 'report.html')], check=True)
subprocess.run(['libreoffice', '--headless', '--convert-to', 'docx', '--outdir', '/home/said/Projects/project-dl-wams', str(ROOT / 'report.odt')], check=True)
print('/home/said/Projects/project-dl-wams/Rapport_WAMS_Apex_Motors_Long.docx')
