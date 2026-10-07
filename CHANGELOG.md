# Changelog

## 1.4.0

- Redact the coordinate-based config entry ID from diagnostics and avoid exposing provider response text in errors.
- Preserve unknown readings; only explicit out-of-season reports without an index fall back to zero.
- Select current readings by UTC date and advance cached data at UTC midnight without additional API requests.
- Normalize UPI categories and validate malformed, empty, and expired forecasts.
- Validate coordinates locally, mask API keys, and distinguish authentication, service, permission, quota, coverage, and temporary failures.
- Add optional tomorrow and upcoming peak sensors for each pollen type, plus an enabled diagnostic last-successful-update timestamp.
- Add per-plant future forecasts and discover plants reported only on future dates.
- Include a built-in-card dashboard example for trends, forecasts, plants, recommendations, and freshness.
- Set the tested minimum Home Assistant version to 2025.4.4 and add a pinned compatibility CI job.

Existing entity unique IDs remain unchanged. Missing in-season readings now report unknown rather than zero. Today and tomorrow use UTC forecast dates. Review templates that previously assumed every plant had a numeric reading.
