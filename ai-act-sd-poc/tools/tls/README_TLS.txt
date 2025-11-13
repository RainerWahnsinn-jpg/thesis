Dev TLS via stunnel (Windows)

Prereq: stunnel installed (https://www.stunnel.org)

1) Generate a self-signed cert (OpenSSL)
   - Open a terminal in tools/tls
   - Run:
     openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"

2) Start stunnel to proxy HTTPS 8443 -> API 8000
   - In tools/tls:
     stunnel stunnel.conf
   - Browser/API URL: https://localhost:8443

3) Point UI/backend to HTTPS (optional)
   - UI env var:
     set BACKEND_URL=https://localhost:8443
   - Accept the self-signed warning in your browser.

Notes
- stunnel.conf expects cert.pem/key.pem in the same folder.
- For production, use a proper certificate and hardened config.
