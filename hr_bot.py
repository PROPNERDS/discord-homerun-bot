import os
import json
import requests
import time
from datetime import datetime, timezone

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
STATE_FILE = "seen_hrs.json"

def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def load_seen():
    if not os.path.exists(STATE_FILE):
        return set()
    try:
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)

def get_json(url, retries=3, wait=2):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"Request failed ({attempt+1}/{retries}): {url} | {e}")
            time.sleep(wait)
    return {}

def discord_post(message):
    try:
        r = requests.post(
            WEBHOOK_URL,
            json={"content": message},
            timeout=15
        )
        print("Discord status:", r.status_code)
    except Exception as e:
        print("Discord post failed:", e)

def get_games():
    schedule_url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={today_str()}"
    data = get_json(schedule_url)
    games = []

    for date in data.get("dates", []):
        for game in date.get("games", []):
            games.append(game["gamePk"])

    print("Games found:", len(games))
    return games

def extract_statcast(play):
    distance = "N/A"
    ev = "N/A"
    la = "N/A"

    for evnt in play.get("playEvents", []):
        hit = evnt.get("hitData", {})
        if hit:
            distance = hit.get("totalDistance", "N/A")
            ev = hit.get("launchSpeed", "N/A")
            la = hit.get("launchAngle", "N/A")
    return distance, ev, la

def check_game(game_pk, seen):
    try:
        url = f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
        data = get_json(url)

        game_data = data.get("gameData", {})
        live_data = data.get("liveData", {})

        venue = game_data.get("venue", {}).get("name", "Unknown Park")
        plays = live_data.get("plays", {}).get("allPlays", [])

        away_runs = live_data.get("linescore", {}).get("teams", {}).get("away", {}).get("runs", 0)
        home_runs = live_data.get("linescore", {}).get("teams", {}).get("home", {}).get("runs", 0)

        for play in plays:
            if play.get("result", {}).get("event") != "Home Run":
                continue

            play_id = f"{game_pk}-{play.get('atBatIndex')}"
            if play_id in seen:
                continue

            batter = play.get("matchup", {}).get("batter", {}).get("fullName", "Unknown Batter")
            pitcher = play.get("matchup", {}).get("pitcher", {}).get("fullName", "Unknown Pitcher")
            inning = play.get("about", {}).get("inning", "?")
            half = play.get("about", {}).get("halfInning", "").title()
            team = play.get("team", {}).get("name", "Unknown Team")
            desc = play.get("result", {}).get("description", "")

            distance, ev, la = extract_statcast(play)

            msg = (
                "🚨⚾ **HOME RUN ALERT** ⚾🚨\n\n"
                f"**{batter}** ({team})\n"
                f"💣 **{distance} FT** | **{ev} MPH EV** | **{la}° LA**\n"
                f"👤 Off: **{pitcher}**\n"
                f"🕒 {half} {inning}\n"
                f"📍 {venue}\n"
                f"📈 Score: Away {away_runs} - Home {home_runs}\n\n"
                f"{desc}\n\n"
                "#PropNerds"
            )

            discord_post(msg)
            seen.add(play_id)

    except Exception as e:
        print(f"Game failed {game_pk}: {e}")

def main():
    print("Starting HR scan...")
    seen = load_seen()
    games = get_games()

    for game_pk in games:
        check_game(game_pk, seen)

    save_seen(seen)
    print("Done.")

if __name__ == "__main__":
    main()
