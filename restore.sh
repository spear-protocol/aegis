set -e

echo "[*] stopping all containers"
if [ "$(docker ps -q)" ];
then
	docker stop $(docker ps -q)
else
	echo "No containers running"
fi
echo "[*] restore previous image"
if [[ -f /home/backup/image ]]
then
    docker load -i /home/backup/image || echo 'image does not exist'
else
	echo "Previous nocust-server image not found"
fi
echo "[*] restore volume from backup"
if [[ -f /home/backup/backup.tar ]]
then
	docker run --rm -v compose_pg-data:/recover -v /home/backup:/backup ubuntu bash -c "cd /recover && tar xvf /backup/backup.tar"
else
	echo "Previous postgresql backup not found"
fi
echo "[*] restart docker containers"
cd /etc/compose && bash run.sh
echo "[*] all good"
