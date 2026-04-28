import os
import json
import requests
from datetime import datetime, timezone

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
STATE_FILE = "seen_hrs.json"

TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
SCHEDULE_URL = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={TODAY}"

def load_seen():
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r") as f:
        return set(json.load(f))

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)

def discord_post(message):
    requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)

def get_games():
    data = requests.get(SCHEDULE_URL, timeout=10).json()
    games = []
    for date in data.get("dates", []):
        for game in date.get("games", []):
            games.append(game["gamePk"])
    return games

def check_game(game_pk, seen):
    url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
    data = requests.get(url, timeout=10).json()

    game_data = data.get("gameData", {})
    live_data = data.get("liveData", {})
    venue = game_data.get("venue", {}).get("name", "Unknown Park")

    all_plays = live_data.get("plays", {}).get("allPlays", [])

    for play in all_plays:
        result = play.get("result", {})
        event = result.get("event", "")

        if event != "Home Run":
            continue

        play_id = f"{game_pk}-{play.get('atBatIndex')}"
        if play_id in seen:
            continue

        batter = play.get("matchup", {}).get("batter", {}).get("fullName", "Unknown Batter")
        pitcher = play.get("matchup", {}).get("pitcher", {}).get("fullName", "Unknown Pitcher")
        inning = play.get("about", {}).get("inning", "?")
        half = play.get("about", {}).get("halfInning", "").title()

        away = live_data.get("linescore", {}).get("teams", {}).get("away", {}).get("runs", 0)
        home = live_data.get("linescore", {}).get("teams", {}).get("home", {}).get("runs", 0)

        team = play.get("team", {}).get("name", "Unknown Team")
        description = result.get("description", "")

        distance = "N/A"
        exit_velo = "N/A"
        launch_angle = "N/A"

        for event_detail in play.get("playEvents", []):
            hit_data = event_detail.get("hitData", {})
            if hit_data:
                distance = hit_data.get("totalDistance", "N/A")
                exit_velo = hit_data.get("launchSpeed", "N/A")
                launch_angle = hit_data.get("launchAngle", "N/A")

        message = (
            "🚨⚾ **HOME RUN ALERT** ⚾🚨\n\n"
            f"**{batter}** ({team})\n"
            f"💣 **{distance} FT** | **{exit_velo} MPH EV** | **{launch_angle}° LA**\n"
            f"👤 Off: **{pitcher}**\n"
            f"🕒 {half} {inning}\n"
            f"📍 {venue}\n"
            f"📈 Score: Away {away} - Home {home}\n\n"
            f"{description}\n\n"
            "#PropNerds"
        )

        discord_post(message)
        seen.add(play_id)

def main():
    seen = load_seen()
    games = get_games()

    for game_pk in games:
        check_game(game_pk, seen)

    save_seen(seen)

if __name__ == "__main__":
    main()
