import os

# Allow importing ag_ui_app in tests without production invoker secret.
os.environ.setdefault("AG_UI_ALLOW_UNAUTHENTICATED", "true")
