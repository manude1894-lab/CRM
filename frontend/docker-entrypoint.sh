#!/bin/sh
# Inject runtime API URL into config.js so Railway can set it via env var
# without needing a rebuild of the frontend image.
cat > /usr/share/nginx/html/config.js << EOF
window.__API_URL__ = '${API_URL:-http://localhost:8000/api/v1}';
EOF

# Railway sets PORT dynamically — update nginx to listen on it
PORT=${PORT:-3000}
sed -i "s/listen [0-9]*/listen ${PORT}/" /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
