"""Central configuration: endpoints, OAuth credentials and file paths.

Every shared constant lives here so it isn't repeated across the code. Secrets
(tokens) are NOT here: they are stored in tokens.json (gitignored).
"""

import os

# --- LaLiga Fantasy API (unofficial) ---
API_BASE = "https://fantasy-api.llt-services.com/api"
COMPETITION_ID = "1"  # LaLiga

# --- OAuth2 Azure B2C (LaLiga login) ---
OAUTH_BASE = "https://login.laliga.es/laligadspprob2c.onmicrosoft.com/oauth2/v2.0"
AUTHORIZE_ENDPOINT = f"{OAUTH_BASE}/authorize"
TOKEN_ENDPOINT = f"{OAUTH_BASE}/token"
SIGNIN_POLICY = "B2C_1A_5ULAIP_PARAMETRIZED_SIGNIN"
CLIENT_ID = "af88bcff-1157-40a0-b579-030728aacf0b"
REDIRECT_URI = "authredirect://com.lfp.laligafantasy"
SCOPE = "openid offline_access"

# --- External sources ---
FF_MARKET_URL = "https://www.futbolfantasy.com/analytics/laliga-fantasy/mercado"
FF_LINEUPS_INDEX = "https://www.futbolfantasy.com/laliga/posibles-alineaciones"
FF_TEAM_URL = "https://www.futbolfantasy.com/laliga/equipos/{slug}"

# Regular browser UA (so we don't give the bot away). Just a label; doesn't affect speed.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

# --- Data paths (tokens, cache, state) ---
# Defaults to the project root (the folder containing the package): convenient
# when running from the checkout. If you install with pip, set FANTASYBOT_HOME to
# avoid writing inside site-packages, e.g. export FANTASYBOT_HOME=~/.fantasybot
ROOT = os.environ.get("FANTASYBOT_HOME") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.expanduser(ROOT)
TOKENS_PATH = os.path.join(ROOT, "tokens.json")
PKCE_PATH = os.path.join(ROOT, ".pkce.json")

# Margin for refreshing the token before it expires (seconds).
TOKEN_EXPIRY_MARGIN = 120
