"""Use the bundled trust store when launched from Finder without a system Python."""
import os

import certifi

os.environ["SSL_CERT_FILE"] = certifi.where()
