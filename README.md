Pour lancer le projet vous avez quelques commandes a faire 

deja telecharger le model .pth qui est dans le lien drive 
https://drive.google.com/drive/folders/1sNTF-pPDOP0UBy6idkOHfX5kx4Cq-WdM?usp=sharing

faire la commande : cp .env.example .env

on a fait un script en bash qui lance tous sa et seed la database et index les images et cree des admins ,
Voici la commande :
bash bootstrap-demo.sh

si sa ne marche pas on peut lancer soit celle la :
docker compose exec product_service python manage.py seed_demo_admin
ou bien celle la :
docker compose exec product_service python manage.py seed_demo

et si l'indexation n'as pas eu lieu 
on utilise cette commande :
docker compose exec product_service python manage.py reindex_product_images --all

et on relance tout avec : docker compose build -d --build

