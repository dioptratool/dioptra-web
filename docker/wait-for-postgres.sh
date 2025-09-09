#!/bin/sh

set -e

cmd="$@"

while ! pg_isready -h "db" -p "5432" > /dev/null 2> /dev/null; do
   echo "Connecting to postgres Failed"
   sleep 1
done

>&2 echo "Postgres is up - executing command"
exec $cmd
