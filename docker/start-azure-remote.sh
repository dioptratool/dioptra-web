#! /bin/sh

# Ensure `www-data` owns any directories in media, so the uwsgi process can write
# into them
find media -type d -exec chown nginx {} \;

# Run database migrations
# python manage.py migrate --noinput

# Start sshd
/usr/sbin/sshd

# Start gunicorn
gunicorn --timeout 90 --access-logfile - --workers 6 --bind unix:/tmp/scan.sock website.wsgi:application &

# Start nginx
nginx -g "daemon off;"
