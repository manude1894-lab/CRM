#!/bin/sh
# Inject runtime API URL into config.js so Railway can set it via env var
# without needing a rebuild of the frontend image.
cat > /usr/share/nginx/html/config.js << EOF
window.__API_URL__ = '${API_URL:-http://localhost:8000/api/v1}';
window.__SITE__ = { privacyUrl: '${PRIVACY_URL:-}', termsUrl: '${TERMS_URL:-}', supportEmail: '${SUPPORT_EMAIL:-}', build: '${RAILWAY_GIT_COMMIT_SHA:-}' };
EOF

# Railway sets PORT dynamically — update nginx to listen on it
PORT=${PORT:-3000}
sed -i "s/listen [0-9]*/listen ${PORT}/" /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
