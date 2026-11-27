#!/usr/bin/env bash
# Linux alternative to tests/team/start-local.ps1 for machines without Docker.
# Starts a local MariaDB (already installed), writes a loopback-only .env, runs
# migrations, creates a synthetic administrator and serves the app on :8000 with
# several PHP workers so concurrent k6 users are not serialised.
# Usage: bash tests/team/usman/start_native.sh   (run from the repository root)
set -euo pipefail
cd "$(dirname "$0")/../../.."
# Database password for the disposable local database: from SQE_DB_PASSWORD, else the existing .env, else random.
DB_PASS="${SQE_DB_PASSWORD:-}"
[[ -z "$DB_PASS" && -f .env ]] && DB_PASS="$(grep '^DB_PASSWORD=' .env | cut -d= -f2-)"
[[ -z "$DB_PASS" ]] && DB_PASS="$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')"

if ! mariadb -uroot -e 'SELECT 1' >/dev/null 2>&1; then
  mkdir -p /run/mysqld && chown mysql:mysql /run/mysqld
  (nohup mysqld_safe --user=mysql >/tmp/sqe-mysqld.log 2>&1 &)
  for _ in $(seq 1 30); do mariadb -uroot -e 'SELECT 1' >/dev/null 2>&1 && break; sleep 1; done
fi
mariadb -uroot -e "CREATE DATABASE IF NOT EXISTS snipeit CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
  CREATE USER IF NOT EXISTS 'snipe'@'127.0.0.1' IDENTIFIED BY '${DB_PASS}';
  CREATE USER IF NOT EXISTS 'snipe'@'localhost' IDENTIFIED BY '${DB_PASS}';
  GRANT ALL ON snipeit.* TO 'snipe'@'127.0.0.1','snipe'@'localhost';"

if [[ ! -f .env ]]; then
  sed -e 's|^APP_URL=.*|APP_URL=http://localhost:8000|' \
      -e 's|^DB_DATABASE=.*|DB_DATABASE=snipeit|' -e 's|^DB_USERNAME=.*|DB_USERNAME=snipe|' \
      -e "s|^DB_PASSWORD=.*|DB_PASSWORD=${DB_PASS}|" -e 's|^MAIL_MAILER=.*|MAIL_MAILER=log|' -e 's|^API_THROTTLE_PER_MINUTE=.*|API_THROTTLE_PER_MINUTE=100000|' \
      -e 's|^MAIL_FROM_ADDR=.*|MAIL_FROM_ADDR=lab@example.test|' -e 's|^MAIL_REPLYTO_ADDR=.*|MAIL_REPLYTO_ADDR=lab@example.test|' \
      .env.example > .env
fi
grep -q '^APP_KEY=ChangeMe' .env && php artisan key:generate --force >/dev/null
php artisan config:clear >/dev/null
if ! mariadb -uroot snipeit -e 'SELECT 1 FROM migrations LIMIT 1' >/dev/null 2>&1; then
  php artisan migrate --force >/dev/null
fi
if ! pgrep -f "php -S 127.0.0.1:8000" >/dev/null; then
  # Laravel's own dev-server router serves existing files (CSS/JS) and sends the rest to index.php.
  (cd public && PHP_CLI_SERVER_WORKERS="${SQE_PHP_WORKERS:-4}" nohup php -S 127.0.0.1:8000 ../vendor/laravel/framework/src/Illuminate/Foundation/resources/server.php >/tmp/sqe-php.log 2>&1 &)
  sleep 2
fi
echo "Snipe-IT is serving on http://localhost:8000 (database snipeit on 127.0.0.1)."
