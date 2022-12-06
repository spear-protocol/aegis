set -e

echo "[*] check backup directory"
if [ ! -d "/home/backup" ] 
then
    mkdir /home/backup
fi
echo "[*] copy env. file"
cp /etc/compose/.env /home/backup/
echo "[*] copy old docker server image"
if [ "$(docker ps -a | grep local-hub-build)" ]
then
    docker save -o /home/backup/image local-hub-build
else
	echo "Previous version of hub not found"
fi
echo "[*] stopping all containers before backup"
if [ "$(docker ps -q)" ];
then
	docker stop $(docker ps -q)
else
	echo "No containers running"
fi
echo "[*] backup Postgresql volume"
if [ "$(docker ps -a | grep compose_db_1)" ]
then
	docker run --rm --volumes-from compose_db_1 -v /home/backup:/backup ubuntu bash -c "cd /var/lib/postgresql/data && tar zcvf /backup/backup.tar ."
	cp /home/backup/backup.tar /home/backup/backup_`date +%d-%m-%Y"_"%H_%M_%S`.tar
else
	echo "No previous Postgres volume found"
fi
echo "[*] run server"
cd /etc/compose && bash run.sh prod
echo "[*] all good"
