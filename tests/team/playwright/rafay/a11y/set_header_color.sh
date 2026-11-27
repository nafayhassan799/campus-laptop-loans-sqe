#!/usr/bin/env bash
# SQE A11Y-06 (configuration fix): the default theme header #3c8dbc gives white text 3.67:1, below the
# WCAG 1.4.3 minimum of 4.5:1 for the logo, the signed-in user name and the footer labels. Snipe-IT's own
# branding setting "Header Color" (Admin > Settings > Branding) drives --main-theme-color; #296282 gives 6.64:1.
#
#   bash tests/team/playwright/rafay/a11y/set_header_color.sh            # apply the fix
#   bash tests/team/playwright/rafay/a11y/set_header_color.sh NULL       # restore the default (the "before" state)
#
# SQE_DB_CMD defaults to the native stack's "mariadb -uroot snipeit"; SQE_ARTISAN to "php artisan".
set -euo pipefail
cd "$(dirname "$0")/../../../../.."
COLOR="${1:-#296282}"
VALUE=$([ "$COLOR" = "NULL" ] && echo "NULL" || echo "'$COLOR'")
${SQE_DB_CMD:-mariadb -uroot snipeit} -e "UPDATE settings SET header_color = ${VALUE}"
${SQE_ARTISAN:-php artisan} cache:clear >/dev/null
echo "header_color set to ${COLOR}"
