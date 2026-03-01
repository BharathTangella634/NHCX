#!/bin/bash

# Configuration
DOMAIN="nhcxhackathon.tanuh.ai"
FRONTEND_PORT="8080"
PDF2FHIRJSON_PORT="8000" # Update with actual port if different
PDF2NHCXJSON_PORT="8001" # Update with actual port if different

CONF_FILE="/etc/apache2/sites-available/${DOMAIN}.conf"

echo "Creating Apache configuration for ${DOMAIN}..."

# Create Apache virtual host configuration
sudo bash -c "cat > ${CONF_FILE}" <<EOF
<VirtualHost *:80>
    ServerName ${DOMAIN}

    # Set timeouts to 25 minutes (1500 seconds)
    Timeout 1500
    ProxyTimeout 1500
    KeepAlive On
    KeepAliveTimeout 1500

    # PDF2FHIRJSON API
    ProxyPass /pdf2fhir http://localhost:${PDF2FHIRJSON_PORT}/pdf2fhir timeout=1500 keepalive=On
    ProxyPassReverse /pdf2fhir http://localhost:${PDF2FHIRJSON_PORT}/pdf2fhir
    # PDF2NHCXJSON API
    ProxyPass /pdf2nhcx http://localhost:${PDF2NHCXJSON_PORT}/pdf2nhcx timeout=1500 keepalive=On
    ProxyPassReverse /pdf2nhcx http://localhost:${PDF2NHCXJSON_PORT}/pdf2nhcx

    # Frontend (Catch-all, should be last)
    ProxyPass / http://localhost:${FRONTEND_PORT}/
    ProxyPassReverse / http://localhost:${FRONTEND_PORT}/

    ErrorLog \${APACHE_LOG_DIR}/${DOMAIN}_error.log
    CustomLog \${APACHE_LOG_DIR}/${DOMAIN}_access.log combined
</VirtualHost>
EOF

echo "Configuring firewall to allow SSH, HTTP, and HTTPS..."
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw allow 443

echo "Enabling necessary Apache modules..."
sudo a2enmod proxy
sudo a2enmod proxy_http
sudo a2enmod rewrite

echo "Enabling site ${DOMAIN}..."
sudo a2ensite ${DOMAIN}

echo "Testing Apache configuration..."
sudo apache2ctl configtest

echo "Restarting Apache2..."
sudo systemctl restart apache2

echo "Apache reverse proxy setup complete for ${DOMAIN}."
echo "- Frontend: http://${DOMAIN}/"
echo "- PDF2FHIRJSON: http://${DOMAIN}/pdf2fhir"
echo "- PDF2NHCXJSON: http://${DOMAIN}/pdf2nhcx"

echo "Installing Certbot for Let's Encrypt (if not already installed)..."
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-apache

echo "Requesting and configuring SSL certificate with Let's Encrypt..."
# Note: You can change the email address admin@\${DOMAIN} to your actual email
sudo certbot --apache -d nhcxhackathon.tanuh.ai --non-interactive --agree-tos -m ashwin.rajkumar@tanuh.ai --no-redirect

echo "Updating SSL VirtualHost configuration to include timeouts..."
SSL_CONF_FILE="/etc/apache2/sites-available/${DOMAIN}-le-ssl.conf"
if [ -f "\$SSL_CONF_FILE" ]; then
    # Add Timeout and ProxyTimeout if not already present
    sudo sed -i '/ServerName.*nhcxhackathon.tanuh.ai/a \ \ \ \ Timeout 1500\n    ProxyTimeout 1500\n    KeepAlive On\n    KeepAliveTimeout 1500' "\$SSL_CONF_FILE"
    
    # Update ProxyPass timeout in SSL conf if it was generated without it
    sudo sed -i 's|ProxyPass /pdf2fhir http://localhost:8000/pdf2fhir.*|ProxyPass /pdf2fhir http://localhost:8000/pdf2fhir timeout=1500 keepalive=On|g' "\$SSL_CONF_FILE"
    sudo sed -i 's|ProxyPass /pdf2nhcx http://localhost:8001/pdf2nhcx.*|ProxyPass /pdf2nhcx http://localhost:8001/pdf2nhcx timeout=1500 keepalive=On|g' "\$SSL_CONF_FILE"
    
    sudo systemctl restart apache2
fi

echo "SSL configuration complete. Your site is now accessible via HTTPS!"
echo "- Frontend: https://${DOMAIN}/"
echo "- PDF2FHIRJSON: https://${DOMAIN}/pdf2fhir"
echo "- PDF2NHCXJSON: https://${DOMAIN}/pdf2nhcx"
