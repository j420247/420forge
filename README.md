# SAML Prerequisites 

For SAML auth you will need to istall the followoing on your OS without this installed the app will not load.
apt-get install libxml2 libxmlsec1
For MacOS you will need to install the developer tools (xcode) and then install libxml2 libxmlsec1

To start the app locally for developemnt do the following in a python3 enviroment: 
* run cloudtoken
* source .env/bin/activate
* pip3 install -r requirements.txt
* python3 acforge.py --nosaml (FOR LOCAL DEV ONLY)
* browse to http://127.0.01:8000 (port 8000 is required for the Centrify My_SAML_app)
** NB: Centrify will not work on 0.0.0.0 or 'localhost', it must be 127.0.0.1

To make the upgrade version check work, you need your browser to allow
ajax requests to external websites.
You can do that with this chrome extension
https://chrome.google.com/webstore/detail/allow-control-allow-origi/nlfbmbojpeacfghkpbjhddihlkkiljbi?hl=en

It's not enabled by default for security reasons.

To run this you now need to:
1. Run the 'update' script from a terminal 