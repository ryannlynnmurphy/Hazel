"""
spotify.py — HZL AI Spotify Integration
Spotipy-based playback control with full debug logging.

Setup:
    pip install spotipy --break-system-packages
    Set env vars: SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
    Authenticate once: python3 spotify.py --auth
"""

import os
import sys
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from hzl_logger import get_logger

log = get_logger("spotify")

# ── Config ────────────────────────────────────────────────────────────────────
CLIENT_ID     = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI  = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
CACHE_PATH    = os.path.expanduser("~/jarvis/.spotify_cache")

SCOPES = " ".join([
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "user-read-recently-played",
    "playlist-read-private",
    "user-library-read",
])


# ── Client factory ────────────────────────────────────────────────────────────
def _client() -> spotipy.Spotify:
    if not CLIENT_ID or not CLIENT_SECRET:
        raise EnvironmentError(
            "Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET in environment."
        )
    auth = SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPES,
        cache_path=CACHE_PATH,
        open_browser=False,
    )
    return spotipy.Spotify(auth_manager=auth)


def _active_device(sp: spotipy.Spotify):
    """Return ID of the active device, or None."""
    devices = sp.devices().get("devices", [])
    log.debug(f"Available devices: {[d['name'] for d in devices]}")
    active = next((d for d in devices if d["is_active"]), None)
    if not active and devices:
        active = devices[0]
        log.debug(f"No active device — defaulting to '{active['name']}'")
    return active["id"] if active else None


# ── Public API ────────────────────────────────────────────────────────────────

def play(query: str = None) -> str:
    log.info(f"play() called — query='{query}'")
    try:
        sp = _client()
        device_id = _active_device(sp)

        if not query:
            sp.start_playback(device_id=device_id)
            log.info("Resumed playback")
            return "Resuming playback."

        results   = sp.search(q=query, limit=5, type="track,playlist")
        tracks    = results.get("tracks", {}).get("items", [])
        playlists = results.get("playlists", {}).get("items", [])

        if tracks:
            track = next((t for t in tracks if t["name"].lower() in query.lower() or any(a["name"].lower() in query.lower() for a in t["artists"])), tracks[0])
            name   = track["name"]
            artist = track["artists"][0]["name"]
            log.info(f"Playing track: '{name}' by {artist} (uri={track['uri']})")
            sp.start_playback(device_id=device_id, uris=[track["uri"]])
            return f"Playing '{name}' by {artist}."

        if playlists:
            pl = playlists[0]
            log.info(f"Playing playlist: '{pl['name']}' (uri={pl['uri']})")
            sp.start_playback(device_id=device_id, context_uri=pl["uri"])
            return f"Playing playlist '{pl['name']}'."

        log.warning(f"No results for query: '{query}'")
        return f"Couldn't find anything matching '{query}' on Spotify."

    except Exception as e:
        log.error(f"play() failed — {e}", exc_info=True)
        return f"Spotify error: {e}"


def pause() -> str:
    log.info("pause() called")
    try:
        _client().pause_playback()
        log.info("Playback paused")
        return "Paused."
    except Exception as e:
        if "403" in str(e) or "Restriction" in str(e):
            return "Already paused."
        log.error(f"pause() failed — {e}", exc_info=True)
        return f"Spotify error: {e}"


def skip() -> str:
    log.info("skip() called")
    try:
        _client().next_track()
        return "Skipped to next track."
    except Exception as e:
        log.error(f"skip() failed — {e}", exc_info=True)
        return f"Spotify error: {e}"


def previous() -> str:
    log.info("previous() called")
    try:
        _client().previous_track()
        return "Going back to previous track."
    except Exception as e:
        log.error(f"previous() failed — {e}", exc_info=True)
        return f"Spotify error: {e}"


def set_volume(level: int) -> str:
    level = max(0, min(100, int(level)))
    log.info(f"set_volume() — level={level}")
    try:
        sp = _client()
        try:
            sp.volume(level, device_id=_active_device(sp))
        except Exception as e:
            if "VOLUME_CONTROL_DISALLOW" in str(e):
                return "Volume control isn't supported on the active device."
            raise
    except Exception as e:
        raise
        return f"Volume set to {level}%."
    except Exception as e:
        log.error(f"set_volume() failed — {e}", exc_info=True)
        return f"Spotify error: {e}"


def now_playing() -> str:
    log.info("now_playing() called")
    try:
        current = _client().current_playback()
        if not current or not current.get("item"):
            return "Nothing is currently playing."
        track    = current["item"]
        name     = track["name"]
        artist   = track["artists"][0]["name"]
        progress = current.get("progress_ms", 0) // 1000
        duration = track.get("duration_ms", 0) // 1000
        log.info(f"Now playing: '{name}' by {artist}")
        return (
            f"Now playing: '{name}' by {artist} "
            f"({progress // 60}:{progress % 60:02d} / {duration // 60}:{duration % 60:02d})."
        )
    except Exception as e:
        log.error(f"now_playing() failed — {e}", exc_info=True)
        return f"Spotify error: {e}"

def now_playing_structured() -> dict:
    """Return full now-playing data including album art URL."""
    log.info("now_playing_structured() called")
    try:
        current = _client().current_playback()
        if not current or not current.get("item"):
            return {"playing": False}
        track    = current["item"]
        name     = track["name"]
        artist   = ", ".join(a["name"] for a in track["artists"])
        album    = track["album"]["name"]
        progress = current.get("progress_ms", 0)
        duration = track.get("duration_ms", 0)
        is_playing = current.get("is_playing", False)
        images   = track["album"].get("images", [])
        art_url  = images[0]["url"] if images else ""
        log.info(f"Now playing structured: '{name}' by {artist}")
        return {
            "playing":  is_playing,
            "title":    name,
            "artist":   artist,
            "album":    album,
            "art":      art_url,
            "progress": progress,
            "duration": duration,
        }
    except Exception as e:
        log.error(f"now_playing_structured() failed — {e}", exc_info=True)
        return {"playing": False, "error": str(e)}

def recently_played(limit: int = 5) -> list:
    """Return recently played tracks with art."""
    log.info("recently_played() called")
    try:
        sp = _client()
        results = sp.current_user_recently_played(limit=limit)
        tracks = []
        for item in results.get("items", []):
            t = item["track"]
            images = t["album"].get("images", [])
            tracks.append({
                "title":  t["name"],
                "artist": t["artists"][0]["name"],
                "album":  t["album"]["name"],
                "art":    images[-1]["url"] if images else "",
                "uri":    t["uri"],
            })
        return tracks
    except Exception as e:
        log.error(f"recently_played() failed — {e}", exc_info=True)
        return []


def queue_track(query: str) -> str:
    log.info(f"queue_track() — query='{query}'")
    try:
        sp      = _client()
        results = sp.search(q=query, limit=1, type="track")
        tracks  = results.get("tracks", {}).get("items", [])
        if not tracks:
            log.warning(f"No track found to queue: '{query}'")
            return f"Couldn't find '{query}' to queue."
        track  = tracks[0]
        sp.add_to_queue(track["uri"])
        log.info(f"Queued: '{track['name']}' by {track['artists'][0]['name']}")
        return f"Added '{track['name']}' by {track['artists'][0]['name']} to queue."
    except Exception as e:
        log.error(f"queue_track() failed — {e}", exc_info=True)
        return f"Spotify error: {e}"



def get_queue(limit: int = 5) -> list:
    """Return upcoming tracks in queue."""
    log.info("get_queue() called")
    try:
        sp = _client()
        result = sp.queue()
        if not result:
            return []
        tracks = []
        for t in (result.get("queue") or [])[:limit]:
            images = t["album"].get("images", [])
            tracks.append({
                "title":  t["name"],
                "artist": t["artists"][0]["name"],
                "album":  t["album"]["name"],
                "art":    images[-1]["url"] if images else "",
                "uri":    t["uri"],
            })
        return tracks
    except Exception as e:
        log.error(f"get_queue() failed — {e}", exc_info=True)
        return []

def get_library(limit: int = 20) -> list:
    """Return saved/liked tracks."""
    log.info("get_library() called")
    try:
        sp = _client()
        results = sp.current_user_saved_tracks(limit=limit)
        tracks = []
        for item in results.get("items", []):
            t = item["track"]
            images = t["album"].get("images", [])
            tracks.append({
                "title":  t["name"],
                "artist": t["artists"][0]["name"],
                "album":  t["album"]["name"],
                "art":    images[-1]["url"] if images else "",
                "uri":    t["uri"],
            })
        return tracks
    except Exception as e:
        log.error(f"get_library() failed — {e}", exc_info=True)
        return []

# ── Auth / test CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--auth" in sys.argv:
        log.info("Starting Spotify auth flow...")
        try:
            sp   = _client()
            user = sp.current_user()
            log.info(f"Authenticated as: {user['display_name']} ({user['id']})")
            print(f"\n  Authenticated as: {user['display_name']}\n")
        except Exception as e:
            log.error(f"Auth failed: {e}", exc_info=True)
            sys.exit(1)
    elif "--test" in sys.argv:
        print(now_playing())
    else:
        print("Usage: python3 spotify.py --auth | --test")
