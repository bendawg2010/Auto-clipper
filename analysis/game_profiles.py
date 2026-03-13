"""
Game-specific detection profiles for the Auto-Clipper.

Each profile defines:
- Color ranges (HSV) for detecting game-specific visual elements
- Screen regions where those elements appear
- Detection weights (what matters most in each game)
- Scoring multipliers and thresholds
- AI prompt text for Grok Vision analysis
"""

import numpy as np


GAME_PROFILES = {
    "arc_raiders": {
        "name": "Arc Raiders",
        "description": "Sci-fi co-op shooter — detects kills, Arc enemies, damage, explosions",

        # Detection components and their HSV color ranges
        "detectors": {
            "kill_feed": {
                "label": "Kill / Elimination",
                "weight": 0.30,
                # Kill notifications: bright white/yellow text top-right
                "lower": np.array([0, 0, 200]),
                "upper": np.array([180, 50, 255]),
                "region": [0.05, 0.25, 0.55, 0.95],  # y1, y2, x1, x2 (as ratio)
                "multiplier": 7,  # density * multiplier, capped at 1.0
            },
            "damage": {
                "label": "Taking Damage",
                "weight": 0.20,
                # Red vignette at screen edges
                "lower": np.array([0, 120, 100]),
                "upper": np.array([10, 255, 255]),
                "lower2": np.array([170, 120, 100]),
                "upper2": np.array([180, 255, 255]),
                "region": "edges",  # special: checks all 4 screen edges
                "edge_size": 0.12,  # 12% of screen from each edge
                "multiplier": 5,
            },
            "hit_marker": {
                "label": "Landing Hits",
                "weight": 0.20,
                # Bright white center crosshair flash
                "lower": np.array([0, 0, 230]),
                "upper": np.array([180, 30, 255]),
                "region": [0.4, 0.6, 0.4, 0.6],  # center screen
                "multiplier": 6,
            },
            "explosion": {
                "label": "Explosion / Combat",
                "weight": 0.18,
                # Orange-yellow muzzle flash / explosions
                "lower": np.array([10, 100, 150]),
                "upper": np.array([35, 255, 255]),
                "region": "full",
                "multiplier": 4,
            },
            "special": {
                "label": "Arc Enemy Encounter",
                "weight": 0.07,
                # Blue glow from Arc enemies
                "lower": np.array([90, 80, 100]),
                "upper": np.array([130, 255, 255]),
                "region": "full",
                "multiplier": 4,
            },
        },

        # Motion detection weight — low to avoid triggering on running/walking
        "motion_weight": 0.03,
        "motion_multiplier": 1.5,

        # Brightness spike weight — low to avoid triggering on menus/inventory
        "brightness_weight": 0.02,
        "brightness_threshold": 0.7,
        "brightness_multiplier": 1.5,

        # Scoring
        "intensity_threshold": 0.35,       # combat-focused: catch more fights
        "fallback_threshold_ratio": 0.3,    # fallback = threshold * this
        "merge_gap": 8,                     # seconds between highlights to merge
        "min_clip_duration": 20,
        "max_clip_duration": 60,
        "clip_extension": 10,
        "pre_pad": 8,

        # AI prompt
        "ai_system_prompt": """You are an expert Arc Raiders gameplay analyst. You analyze screenshots from Arc Raiders streams to identify exciting moments worth clipping.

Look for these types of highlights:
- **Kills**: Player eliminating Arc enemies (robots), leapers, or other threats
- **Combat**: Active gunfights, shooting at enemies, taking fire
- **Arc Encounters**: Large Arc enemy appearances, boss-like encounters
- **Explosions**: Big explosions, grenades, environmental destruction
- **Close Calls**: Player at low health, narrow escapes
- **Loot/Rewards**: Finding rare loot, extraction moments
- **Deaths**: Player dying (also exciting/funny content)

For each frame, respond with ONLY a JSON object (no markdown):
{"exciting": true/false, "score": 0.0-1.0, "label": "short description", "reason": "brief reason"}

Score guide: 0.0 = nothing happening, 0.3 = minor action, 0.6 = good combat, 0.8 = kill/major moment, 1.0 = insane play""",
        "ai_user_prompt": "Analyze this Arc Raiders gameplay frame. Is this an exciting moment?",
    },

    "war_thunder": {
        "name": "War Thunder",
        "description": "Military vehicles — detects kills, crits, fires, bomb hits, air kills",

        "detectors": {
            "kill_feed": {
                "label": "Target Destroyed",
                "weight": 0.30,
                # War Thunder kill text: bright yellow/white text center-bottom area
                # "Target Destroyed", "Critical hit", "Hit" messages
                "lower": np.array([18, 80, 200]),
                "upper": np.array([35, 255, 255]),
                # Also check for white text
                "lower2": np.array([0, 0, 220]),
                "upper2": np.array([180, 40, 255]),
                "region": [0.55, 0.85, 0.25, 0.75],  # lower-center where kill msgs appear
                "multiplier": 5,
            },
            "damage": {
                "label": "Taking Damage",
                "weight": 0.15,
                # Red damage flash / screen shake indicator
                "lower": np.array([0, 100, 80]),
                "upper": np.array([12, 255, 255]),
                "lower2": np.array([168, 100, 80]),
                "upper2": np.array([180, 255, 255]),
                "region": "edges",
                "edge_size": 0.12,
                "multiplier": 4,
            },
            "hit_marker": {
                "label": "Critical Hit",
                "weight": 0.15,
                # Crosshair hit confirmation - bright center flash
                "lower": np.array([0, 0, 235]),
                "upper": np.array([180, 25, 255]),
                "region": [0.35, 0.65, 0.35, 0.65],
                "multiplier": 5,
            },
            "explosion": {
                "label": "Explosion / Bomb Hit",
                "weight": 0.20,
                # Vehicle explosions, bomb blasts — large orange-red bursts
                "lower": np.array([5, 100, 130]),
                "upper": np.array([30, 255, 255]),
                "region": "full",
                "multiplier": 3,
            },
            "special": {
                "label": "Vehicle on Fire",
                "weight": 0.10,
                # Fire/smoke from burning vehicles — orange-red with high saturation
                "lower": np.array([0, 130, 140]),
                "upper": np.array([20, 255, 255]),
                "region": "full",
                "multiplier": 3,
            },
        },

        "motion_weight": 0.07,
        "motion_multiplier": 3,

        "brightness_weight": 0.03,
        "brightness_threshold": 0.65,
        "brightness_multiplier": 2.5,

        # War Thunder has slower-paced moments, use slightly lower threshold
        "intensity_threshold": 0.35,
        "fallback_threshold_ratio": 0.5,
        "merge_gap": 10,
        "min_clip_duration": 20,
        "max_clip_duration": 60,
        "clip_extension": 10,
        "pre_pad": 6,

        "ai_system_prompt": """You are an expert War Thunder gameplay analyst. You analyze screenshots from War Thunder streams to identify exciting moments worth clipping.

War Thunder is a military vehicle combat game with tanks, planes, ships, and helicopters. Look for:

- **Kills**: "Target Destroyed" messages, enemy vehicles exploding, turrets flying off
- **Critical Hits**: Penetrating shots, ammo rack detonations, one-shot kills
- **Bomb/Rocket Hits**: Air-to-ground strikes, carpet bombing, rocket runs
- **Air Combat**: Dogfights, plane-on-plane kills, anti-air shoots down plane
- **Close Calls**: Near-miss shells, surviving a bomb, clutch repair
- **Vehicle on Fire**: Tanks burning, planes trailing smoke, emergency landings
- **Multi-kills**: Killing several enemies in quick succession
- **Deaths**: Player getting destroyed (can also be funny/dramatic)
- **Sniper Shots**: Long-range kills, satisfying crosshair placement

For each frame, respond with ONLY a JSON object (no markdown):
{"exciting": true/false, "score": 0.0-1.0, "label": "short description", "reason": "brief reason"}

Score guide: 0.0 = driving around doing nothing, 0.3 = minor combat, 0.6 = good hit or near-miss, 0.8 = kill/destruction, 1.0 = insane multi-kill or clutch play""",
        "ai_user_prompt": "Analyze this War Thunder gameplay frame. Is this an exciting moment?",
    },
}


def get_profile(game_id):
    """Get a game profile by ID. Falls back to arc_raiders if not found."""
    return GAME_PROFILES.get(game_id, GAME_PROFILES["arc_raiders"])


def get_all_games():
    """Return a list of available games for the UI."""
    return [
        {"id": game_id, "name": profile["name"], "description": profile["description"]}
        for game_id, profile in GAME_PROFILES.items()
    ]
