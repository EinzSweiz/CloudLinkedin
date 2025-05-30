import zipfile
import os
import uuid
import logging

logger = logging.getLogger(__name__)

def create_proxy_auth_extension(proxy_host, proxy_port, proxy_username, proxy_password, save_dir="/tmp") -> str:
    """
    Creates a proxy auth plugin ZIP inside the project folder (or Docker volume)
    and returns the absolute path to it.
    """
    logger.info(f"[PLUGIN START] Creating proxy plugin for: {proxy_host}:{proxy_port} ({proxy_username})")

    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Proxy Authentication Extension",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        }
    }
    """

    background_js = f"""
    var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "http",
                    host: "{proxy_host}",
                    port: parseInt({proxy_port})
                }},
                bypassList: ["localhost"]
            }}
        }};
    
    chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
    
    function callbackFn(details) {{
        return {{
            authCredentials: {{
                username: "{proxy_username}",
                password: "{proxy_password}"
            }}
        }};
    }}
    
    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {{urls: ["<all_urls>"]}},
        ['blocking']
    );
    """

    try:
        filename = f"proxy_auth_plugin_{uuid.uuid4().hex}.zip"
        plugin_path = os.path.abspath(os.path.join(save_dir, filename))

        logger.debug(f"[PLUGIN FILE] Full path: {plugin_path}")
        os.makedirs(save_dir, exist_ok=True)

        with zipfile.ZipFile(plugin_path, 'w') as zp:
            zp.writestr("manifest.json", manifest_json)
            zp.writestr("background.js", background_js)
        logger.info(f"[PLUGIN DONE] Plugin created: {plugin_path}")

        if os.path.exists(plugin_path):
            return plugin_path
        else:
            logger.error(f"[PLUGIN ERROR] File was not created at {plugin_path}")
            raise ValueError("Proxy plugin creation failed")

    except Exception as e:
        logger.exception(f"[PLUGIN EXCEPTION] Error during plugin creation: {e}")
        raise
