#!/bin/bash

# This script can be used as example of how to migrate the database.
# As every system is a bit different, nobody can guarantee that this
# exact script will work. However the general idea of running two
# postgres docker containers with intra-connected backup folder
# used to gather the export of version 13 to be imported into
# version 16 works well.

read -p "Are you sure? (Y/n)" -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
  echo "Let's migrate!"
else
  exit
fi

set -a
. ./.env
set +a

docker-compose down

docker-compose -f upgrade-postgres.yml up -d

sleep 15s

container_13_id="$( docker ps -a | grep ${INSTANCE_NAME}-dbold | cut -d' ' -f1)"
container_16_id="$( docker ps -a | grep ${INSTANCE_NAME}-dbupgrade | cut -d' ' -f1)"

docker exec -it $container_13_id /bin/bash -c "pg_dumpall -U ${DB_USER} > /backup/backup.sql"

docker exec -it $container_16_id /bin/bash -c "psql -d ${DB_NAME} -U ${DB_USER} < /backup/backup.sql"

docker exec -it $container_16_id /bin/bash -c "echo ALTER USER ${DB_USER} WITH PASSWORD \'${DB_PASSWORD}\' > /backup/reset.txt"

docker exec -it $container_16_id /bin/bash -c "psql -U ${DB_USER} < /backup/reset.txt"

docker exec -it $container_16_id /bin/bash -c "rm /backup/reset.txt"
docker exec -it $container_16_id /bin/bash -c "rm /backup/backup.sql"

docker-compose -f upgrade-postgres.yml down

echo "DONE!"
