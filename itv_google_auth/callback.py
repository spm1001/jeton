"""HTML templates for OAuth callback pages."""

SUCCESS_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Authorization Successful</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            text-align: center;
            padding: 50px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 400px;
            margin: 0 auto;
        }
        h1 { color: #2e7d32; margin-bottom: 20px; }
        p { color: #666; line-height: 1.6; }
    </style>
</head>
<body>
    <div class="container">
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
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            text-align: center;
            padding: 50px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 400px;
            margin: 0 auto;
        }
        h1 { color: #d32f2f; margin-bottom: 20px; }
        p { color: #666; line-height: 1.6; }
        .error { color: #d32f2f; font-family: monospace; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Authorization Failed</h1>
        <p class="error">{error}</p>
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
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            text-align: center;
            padding: 50px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 400px;
            margin: 0 auto;
        }
        h1 { color: #d32f2f; margin-bottom: 20px; }
        p { color: #666; line-height: 1.6; }
    </style>
</head>
<body>
    <div class="container">
        <h1>No Authorization Code</h1>
        <p>The callback did not contain an authorization code.</p>
        <p>Please try the authorization flow again.</p>
    </div>
</body>
</html>
"""

POST_AUTH_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Authorization Successful</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            text-align: center;
            padding: 50px;
            background: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            max-width: 500px;
            margin: 0 auto;
        }}
        h1 {{ color: #2e7d32; margin-bottom: 20px; }}
        p {{ color: #666; line-height: 1.6; }}
        .copy-section {{
            background: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            padding: 20px;
            margin: 20px 0;
        }}
        .copy-label {{
            font-size: 14px;
            color: #666;
            margin-bottom: 8px;
        }}
        .copy-value {{
            font-family: 'SF Mono', Monaco, 'Courier New', monospace;
            font-size: 18px;
            font-weight: 600;
            color: #1a73e8;
            background: white;
            padding: 12px 16px;
            border-radius: 4px;
            border: 1px solid #dadce0;
            display: inline-block;
            user-select: all;
            cursor: pointer;
        }}
        .copy-value:hover {{
            background: #e8f0fe;
        }}
        .copy-hint {{
            font-size: 12px;
            color: #999;
            margin-top: 8px;
        }}
        .message {{
            color: #5f6368;
            margin: 20px 0;
            line-height: 1.6;
        }}
        .button {{
            display: inline-block;
            background: #1a73e8;
            color: white;
            padding: 12px 24px;
            border-radius: 4px;
            text-decoration: none;
            font-weight: 500;
            margin-top: 16px;
            transition: background 0.2s;
        }}
        .button:hover {{
            background: #1557b0;
        }}
        .copied {{
            color: #2e7d32;
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
