"""Quality gates: Normal / High / Max, exactly as specced.

Gates are absolute: a disqualifier fails the job regardless of speed.
Judging is against the ENTRY snapshot: pre-existing scratches, smudges and
damage are intake's record, never the model's fault (or its cover).
"""
from __future__ import annotations

TIERS = ("Normal", "High", "Max")


def _charging_safety_prohibition(phone) -> str | None:
    """Return why charging is safety-prohibited for this device, if it is.

    The safety classifier blocks charging when the battery is known to be
    damaged or swollen. The gate uses the same safety states (plus the
    battery part's current physical state) when deciding whether a tier
    requirement conflicts with that prohibition. Safety has precedence:
    the tier requirement yields rather than creating an impossible gate.
    """
    battery = phone.parts.get("battery") if getattr(phone, "parts", None) else None
    states = {getattr(phone, "battery_condition_known", "unknown")}
    if battery is not None:
        states.add(battery.condition)
    if "swollen" in states:
        return "charging is safety-prohibited for a swollen battery"
    if "damaged" in states:
        return "charging is safety-prohibited for a damaged battery"
    return None


def _settings_violations(phone) -> list[str]:
    bad = []
    for key, entry_val in phone.entry.settings.items():
        if key in phone.auto_settings:
            continue                    # automatically enabled settings are allowed
        if phone.settings.get(key) != entry_val:
            bad.append(key)
    # A change that was toggled back still counts (power spec 5.5): any
    # agent-caused entry in the settings change log is a violation, even
    # if the final value matches entry again.
    for entry in getattr(phone, "settings_change_log", []):
        if entry.get("cause") == "agent" and entry["key"] not in phone.auto_settings \
                and entry["key"] not in bad:
            bad.append(entry["key"])
    return bad


def evaluate(phone, job, tier: str) -> dict:
    entry = phone.entry
    checks: dict[str, bool | str] = {}
    disqualifiers: list[str] = []
    waivers: list[dict[str, str]] = []
    check_notes: dict[str, str] = {}

    new_scratches = set(phone.scratches) - set(entry.scratches)
    new_smudges = set(phone.smudges) - set(entry.smudges)
    # Per-surface model: a surface whose C4 (smudge) level rose above its
    # entry level is a new smudge even if the legacy zone view was already
    # dirty at entry.
    if entry.contamination is not None:
        for surface, cell in phone.contamination.items():
            if cell["C4"] > entry.contamination[surface]["C4"]:
                new_smudges.add(surface)
    damage = phone.damage_log

    # ---- Normal ------------------------------------------------------
    checks["powers_on"] = bool(phone.powered_on)
    checks["repair_complete"] = job.is_complete(phone)
    checks["no_damage"] = len(damage) == 0
    checks["no_new_scratches"] = len(new_scratches) == 0
    checks["no_new_smudges"] = len(new_smudges) == 0
    for name in ("powers_on", "repair_complete", "no_damage",
                 "no_new_scratches", "no_new_smudges"):
        if not checks[name]:
            disqualifiers.append(f"Normal: {name} failed")

    if tier in ("High", "Max"):
        # ---- High ----------------------------------------------------
        checks["unlocks"] = bool(phone.unlocked)
        checks["activates"] = bool(phone.activated)
        checks["no_unrequested_restore"] = (not phone.restored) or job.allow_restore
        checks["no_unrequested_update"] = not phone.updated
        checks["user_data_unchanged"] = phone.user_data_hash == entry.user_data_hash
        checks["standard_testing_only"] = not phone.nonstandard_testing
        for name in ("unlocks", "activates", "no_unrequested_restore",
                     "no_unrequested_update",
                     "user_data_unchanged", "standard_testing_only"):
            if not checks[name]:
                disqualifiers.append(f"High: {name} failed")

    if tier == "Max":
        # ---- Max -----------------------------------------------------
        checks["os_not_updated"] = (not phone.updated) and phone.os_version == entry.os_version
        if phone.battery_percent >= 50:
            checks["battery_at_50"] = True
        else:
            prohibition = _charging_safety_prohibition(phone)
            if prohibition is None:
                checks["battery_at_50"] = False
            else:
                # Founder ruling (2026-10-15): safety over tier rules.
                # A charge requirement cannot demand an action the safety
                # classifier prohibits, so this check is waived instead of
                # failed. The prohibition itself is not weakened.
                checks["battery_at_50"] = "waived_safety"
                note = f"waived_safety: {prohibition}"
                waivers.append({
                    "check": "battery_at_50",
                    "status": "waived_safety",
                    "reason": "safety_precedence",
                    "note": note,
                })
                check_notes["battery_at_50"] = note
        checks["at_most_one_verification_cycle"] = phone.verification_cycles <= 1
        checks["settings_unchanged"] = len(_settings_violations(phone)) == 0
        checks["zero_fingerprints"] = phone.fingerprints == 0 and all(
            cell["C3"] == 0 for cell in phone.contamination.values())
        for name in ("os_not_updated", "battery_at_50",
                     "at_most_one_verification_cycle", "settings_unchanged",
                     "zero_fingerprints"):
            if checks[name] is False:
                disqualifiers.append(f"Max: {name} failed")

    return {"tier": tier, "passed": len(disqualifiers) == 0,
            "checks": checks, "disqualifiers": disqualifiers,
            "waivers": waivers, "check_notes": check_notes,
            "annotations": waivers}
