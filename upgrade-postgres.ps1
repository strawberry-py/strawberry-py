get-content .env | ForEach-Object {
    if ($_ -like "*=*") {
		$name, $value = $_.split('=',[System.StringSplitOptions]::RemoveEmptyEntries)
		set-content env:$name $value
	}
}

docker-compose down

docker compose -f upgrade-postgres.yml up -d

Start-Sleep 15

docker compose -f upgrade-postgres.yml exec -it db_postgres_13 /bin/bash -c "pg_dumpall -U $($ENV:DB_USER) > /backup/backup.sql"

docker compose -f upgrade-postgres.yml exec -it db_postgres_16 /bin/bash -c "psql -d $($ENV:DB_NAME) -U $($ENV:DB_USER) < /backup/backup.sql"

docker compose -f upgrade-postgres.yml exec -it db_postgres_16 /bin/bash -c "echo ALTER USER $($ENV:DB_USER) WITH PASSWORD \'$($ENV:DB_PASSWORD)\' > /backup/reset.txt"

docker compose -f upgrade-postgres.yml exec -it db_postgres_16 /bin/bash -c "psql -U $($ENV:DB_USER) < /backup/reset.txt"

docker compose -f upgrade-postgres.yml exec -it db_postgres_16 /bin/bash -c "rm /backup/reset.txt"
docker compose -f upgrade-postgres.yml exec -it db_postgres_16 /bin/bash -c "rm /backup/backup.txt"

docker compose -f upgrade-postgres.yml down

Write-Output "DONE!"
Read-Host
