// Runtime configuration for the Hermes static frontend.
// A container can override this file (e.g. bind-mount / generate at
// startup) to point the UI at a different backend without a rebuild.
window.BACKEND_URL = window.BACKEND_URL || "http://localhost:8000";
