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
        <h1>Authorization Received!</h1>
        <p>Processing your authorization...</p>
        <p>Check your terminal for completion status.</p>
        <p style="color: #999; font-size: 14px;">This window will close automatically.</p>
    </div>
    <script>
        setTimeout(() => {
            try { window.close(); } catch(e) {}
        }, 3000);
    </script>
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
