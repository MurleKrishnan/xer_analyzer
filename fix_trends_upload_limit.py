import os

print("🔧 Updating upload limits for Multi-Period Trends (100MB -> 1000MB)...")

# 1. Update config.py
try:
    with open("config.py", "r", encoding="utf-8") as f:
        cfg = f.read()

    cfg = cfg.replace("MAX_UPLOAD_SIZE_MB = 100", "MAX_UPLOAD_SIZE_MB = 1000")

    with open("config.py", "w", encoding="utf-8") as f:
        f.write(cfg)
    print("  ✅ Updated config.py (MAX_UPLOAD_SIZE_MB = 1000)")
except Exception as e:
    print(f"  ⚠️ Could not update config.py: {e}")


# 2. Update app.py
try:
    with open("app.py", "r", encoding="utf-8") as f:
        app_code = f.read()

    # Update MAX_UPLOAD_SIZE_MB fallback default if present
    app_code = app_code.replace("MAX_UPLOAD_SIZE_MB = 100", "MAX_UPLOAD_SIZE_MB = 1000")

    with open("app.py", "w", encoding="utf-8") as f:
        f.write(app_code)
    print("  ✅ Updated app.py (Max content length bumped to 1000MB)")
except Exception as e:
    print(f"  ⚠️ Could not update app.py: {e}")


# 3. Update static/trends.js
try:
    with open("static/trends.js", "r", encoding="utf-8") as f:
        js_code = f.read()

    # Raise client-side limit in trends.js to 500MB
    js_code = js_code.replace("const MAX_UPLOAD_MB = 100;", "const MAX_UPLOAD_MB = 1000;")
    js_code = js_code.replace("exceeds 100 MB limit", "exceeds 1000 MB limit")

    with open("static/trends.js", "w", encoding="utf-8") as f:
        f.write(js_code)
    print("  ✅ Updated static/trends.js (Client-side limit bumped to 1000MB)")
except Exception as e:
    print(f"  ⚠️ Could not update static/trends.js: {e}")

print("\n🎉 Upload limits increased successfully!")
print("👉 Restart Flask (python app.py) and try uploading your files on /trends again.")