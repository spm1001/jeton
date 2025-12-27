"""HTML templates for OAuth callback pages with ITV branding."""

# ITV Brand color tokens (from itv-brand skill)
_ITV_BRAND_CSS = """
    :root {
        --itv-dark-bg: #0F2323;
        --itv-yellow: #E8E557;
        --itv-teal: #4ECDC4;
        --itv-teal-light: #7EE8E0;
        --white: #FFFFFF;
        --white-60: rgba(255,255,255,0.6);
        --white-40: rgba(255,255,255,0.4);
        --error-red: #FF6B6B;
    }
    * { box-sizing: border-box; }
    body {
        font-family: 'Public Sans', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
        text-align: center;
        padding: 50px 20px;
        margin: 0;
        background: var(--itv-dark-bg);
        min-height: 100vh;
    }
    .container {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        padding: 40px;
        border-radius: 8px;
        max-width: 500px;
        margin: 0 auto;
    }
    .icon {
        width: 64px;
        height: 64px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 24px auto;
    }
    .icon svg {
        width: 32px;
        height: 32px;
        stroke-width: 3;
        fill: none;
    }
    .icon-success {
        background: var(--itv-teal);
    }
    .icon-success svg {
        stroke: var(--itv-dark-bg);
    }
    .icon-error {
        background: rgba(255,107,107,0.15);
        border: 2px solid var(--error-red);
    }
    .icon-error svg {
        stroke: var(--error-red);
    }
    h1 {
        font-size: 28px;
        font-weight: 700;
        margin: 0 0 16px 0;
    }
    .success h1 { color: var(--itv-yellow); }
    .error h1 { color: var(--error-red); }
    p {
        color: var(--white-60);
        font-size: 16px;
        line-height: 1.6;
        margin: 0;
    }
    .error-message {
        font-family: 'SF Mono', Monaco, 'Courier New', monospace;
        color: var(--error-red);
        background: rgba(255,107,107,0.1);
        padding: 12px 16px;
        border-radius: 6px;
        font-size: 14px;
        margin: 16px 0;
    }
"""

SUCCESS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Authorization Successful</title>
    <style>""" + _ITV_BRAND_CSS + """
    </style>
</head>
<body>
    <div class="container success">
        <div class="icon icon-success">
            <svg viewBox="0 0 24 24">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
        </div>
        <h1>Authorization Successful!</h1>
        <p>You can close this tab and return to your terminal.</p>
    </div>
</body>
</html>
"""

ERROR_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Authorization Failed</title>
    <style>""" + _ITV_BRAND_CSS + """
    </style>
</head>
<body>
    <div class="container error">
        <div class="icon icon-error">
            <svg viewBox="0 0 24 24">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </div>
        <h1>Authorization Failed</h1>
        <div class="error-message">{error}</div>
        <p>You can close this window and check your terminal.</p>
    </div>
</body>
</html>
"""

NO_CODE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>No Authorization Code</title>
    <style>""" + _ITV_BRAND_CSS + """
    </style>
</head>
<body>
    <div class="container error">
        <div class="icon icon-error">
            <svg viewBox="0 0 24 24">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </div>
        <h1>No Authorization Code</h1>
        <p>The callback did not contain an authorization code.</p>
        <p style="margin-top: 12px;">Please try the authorization flow again.</p>
    </div>
</body>
</html>
"""

# Note: POST_AUTH_HTML uses double braces {{}} for CSS since it's a format string
POST_AUTH_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Authorization Successful</title>
    <style>
    :root {{
        --itv-dark-bg: #0F2323;
        --itv-yellow: #E8E557;
        --itv-teal: #4ECDC4;
        --itv-teal-light: #7EE8E0;
        --white: #FFFFFF;
        --white-60: rgba(255,255,255,0.6);
        --white-40: rgba(255,255,255,0.4);
    }}
    * {{ box-sizing: border-box; }}
    body {{
        font-family: 'Public Sans', system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
        text-align: center;
        padding: 50px 20px;
        margin: 0;
        background: var(--itv-dark-bg);
        min-height: 100vh;
    }}
    .container {{
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.08);
        padding: 40px;
        border-radius: 8px;
        max-width: 500px;
        margin: 0 auto;
    }}
    .icon {{
        width: 64px;
        height: 64px;
        background: var(--itv-teal);
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 24px auto;
    }}
    .icon svg {{
        width: 32px;
        height: 32px;
        stroke: var(--itv-dark-bg);
        stroke-width: 3;
        fill: none;
    }}
    h1 {{
        color: var(--itv-yellow);
        font-size: 28px;
        font-weight: 700;
        margin: 0 0 16px 0;
    }}
    p {{
        color: var(--white-60);
        font-size: 16px;
        line-height: 1.6;
        margin: 0;
    }}
    .copy-section {{
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 6px;
        padding: 20px;
        margin: 24px 0;
    }}
    .copy-label {{
        font-size: 13px;
        color: var(--white-40);
        margin-bottom: 8px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .copy-value {{
        font-family: 'SF Mono', Monaco, 'Courier New', monospace;
        font-size: 20px;
        font-weight: 600;
        color: var(--itv-teal);
        background: rgba(78,205,196,0.1);
        padding: 12px 16px;
        border-radius: 4px;
        border: 1px solid rgba(78,205,196,0.3);
        display: inline-block;
        cursor: pointer;
        user-select: all;
        transition: all 0.2s;
    }}
    .copy-value:hover {{
        background: rgba(78,205,196,0.2);
        border-color: var(--itv-teal);
    }}
    .copy-hint {{
        font-size: 12px;
        color: var(--white-40);
        margin-top: 8px;
    }}
    .message {{
        color: var(--white-60);
        margin: 20px 0;
        line-height: 1.6;
    }}
    .button {{
        display: inline-block;
        background: var(--itv-teal);
        color: var(--itv-dark-bg);
        padding: 14px 28px;
        border-radius: 6px;
        text-decoration: none;
        font-weight: 600;
        font-size: 15px;
        margin-top: 8px;
        transition: all 0.2s;
    }}
    .button:hover {{
        background: var(--itv-teal-light);
    }}
    .copied {{
        color: var(--itv-yellow);
        font-size: 14px;
        margin-top: 8px;
        opacity: 0;
        transition: opacity 0.2s;
    }}
    .copied.show {{
        opacity: 1;
    }}
    </style>
</head>
<body>
    <div class="container">
        <div class="icon">
            <svg viewBox="0 0 24 24">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
        </div>
        <h1>Authorization Successful!</h1>
        <div class="copy-section">
            <div class="copy-label">{copy_label}</div>
            <div class="copy-value" id="copyValue" onclick="copyToClipboard()">{copy_value}</div>
            <div class="copy-hint">Click to copy</div>
            <div class="copied" id="copiedMsg">Copied!</div>
        </div>
        <p class="message">{message}</p>
        <a href="{button_url}" target="_blank" class="button">{button_label}</a>
    </div>
    <script>
        function copyToClipboard() {{
            const value = document.getElementById('copyValue').textContent;
            navigator.clipboard.writeText(value).then(() => {{
                const msg = document.getElementById('copiedMsg');
                msg.classList.add('show');
                setTimeout(() => msg.classList.remove('show'), 2000);
            }});
        }}
    </script>
</body>
</html>
"""
