"""Display touch tool (`dt_`): the agent's finger, via screen mirroring.

Implements tool-specs/display-touch.md. The phone can be connected to
screen mirroring; while the mirror is live the agent SEES the screen
through the mirror feed (observe() returns a screen-state description)
and TOUCHES it through this tool (dt_tap / dt_swipe / dt_long_press on
named screen elements). With no mirror connected the screen is dark to
the agent: touches are blind and error-prone.

Screen state is derived from device state (power / unlock / activation /
passcode). A passcode-locked phone shows a keypad after swipe-up and
stays locked: the tool never knows, requests, or stores a credential,
so unlock verification on such a phone is `inconclusive` (power spec
§5.4 / open question 2, addressed by design for no-credential and
standard-flow cases).
"""
from __future__ import annotations


def screen_state(phone) -> dict:
    """What the mirror feed shows right now."""
    if not phone.powered_on:
        return {"visible": False, "screen": "off", "elements": [],
                "lock_state": "off", "activation": "unknown"}
    if not phone.unlocked:
        if getattr(phone, "_passcode_prompt", False):
            return {"visible": True, "screen": "passcode_prompt",
                    "elements": ["passcode_keypad", "cancel_button"],
                    "lock_state": "passcode_required",
                    "activation": "pending" if not phone.activated else "activated"}
        return {"visible": True, "screen": "lock_screen",
                "elements": ["clock", "swipe_up_affordance", "flashlight_icon",
                             "camera_icon"],
                "lock_state": "locked",
                "activation": "pending" if not phone.activated else "activated"}
    if not phone.activated:
        return {"visible": True, "screen": "activation_screen",
                "elements": ["hello_text", "continue_button", "language_picker"],
                "lock_state": "unlocked", "activation": "pending"}
    return {"visible": True, "screen": "home_screen",
            "elements": ["home_screen", "app_icons", "dock", "control_center_handle"],
            "lock_state": "unlocked", "activation": "activated"}


class DisplayTouch:
    """State for the dt_ tool: mirror connection + tool mounting, plus
    the mirror-lag bookkeeping (the feed the agent acts on can be one
    frame behind a state change)."""

    def __init__(self):
        self.mirror_connected = False
        self.tool_mounted = False
        self.last_frame_time = -1e9       # sim time of the frame being viewed
        self.last_frame_elements: list = []
        self.taps = 0
        self.swipes = 0
        self.long_presses = 0
        self.blind_touches = 0
        self.missed_touches = 0
        self.stale_frame_events = 0

    def state(self) -> dict:
        return {"mirror_connected": self.mirror_connected,
                "tool_mounted": self.tool_mounted,
                "taps": self.taps, "swipes": self.swipes,
                "long_presses": self.long_presses,
                "blind_touches": self.blind_touches,
                "missed_touches": self.missed_touches,
                "stale_frame_events": self.stale_frame_events}
