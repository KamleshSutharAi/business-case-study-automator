import os
import json
import requests
import subprocess
from google import genai
from google.genai import types

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")

if not GEMINI_KEY or not PEXELS_KEY:
    raise ValueError("Missing API keys. Check GitHub Secrets.")

client = genai.Client(api_key=GEMINI_KEY)

# Target runtime window in seconds
TARGET_MIN_SECONDS = 480   # 8 minutes
TARGET_MAX_SECONDS = 600   # 10 minutes
WORDS_PER_SECOND = 2.65    # ~159 wpm for en-US-ChristopherNeural at +5% rate


def generate_script(topic):
    prompt = f"""
    You are an elite YouTube documentary producer for a high-RPM American finance channel.
    Write a comprehensive, hyper-engaging 15-scene documentary script about: {topic}.

    RULES FOR 8-10 MINUTE RETENTION (US AUDIENCE):
    1. Scene 1 MUST start with a shocking 3-second hook (e.g., a massive dollar amount, a fatal business mistake).
    2. Write in punchy, dramatic American English. Use high-stakes storytelling to keep viewers hooked for 10 minutes.
    3. LENGTH REQUIREMENT: Every scene's narration MUST be AT LEAST 110 words. There is no upper limit -
       longer, more detailed scenes are preferred. Do not pad with filler; add real detail, numbers, and story beats.
    4. broll_keyword must be a 2-4 word VISUAL search phrase describing what should be ON SCREEN during
       THIS specific scene's narration - not a generic mood word. Base it on the concrete subject of the
       scene (e.g. for a scene about store closures: "empty retail store"; for layoffs: "office layoffs boxes";
       for a stock crash: "stock market crash graph"). Avoid single abstract words like "panic" or "money" alone.

    Return your response strictly as valid JSON matching this format:
    {{
        "title": "Compelling Title",
        "description": "Engaging description with tags",
        "scenes": [
            {{
                "scene_number": 1,
                "narration": "Long, detailed, high-stakes narration...",
                "broll_keyword": "keyword"
            }}
        ]
    }}
    """

    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8,
            max_output_tokens=8000,
        )
    )
    return json.loads(response.text)


def expand_scene(topic, scene, current_words, min_words):
    """Ask the model to rewrite a single scene so it's long enough, keeping the same beat/keyword."""
    prompt = f"""
    You are rewriting ONE scene of a documentary script about: {topic}.

    Here is the current narration for scene {scene['scene_number']} (only {current_words} words):
    ---
    {scene['narration']}
    ---

    Rewrite it to be AT LEAST {min_words} words. Keep the same core point and the same dramatic,
    punchy American documentary tone. Add specific details, numbers, consequences, or a short anecdote
    to extend it naturally - do not just repeat sentences or pad with filler.

    Keep the same broll_keyword: "{scene['broll_keyword']}".

    Return ONLY valid JSON in this exact format, nothing else:
    {{
        "scene_number": {scene['scene_number']},
        "narration": "expanded narration...",
        "broll_keyword": "{scene['broll_keyword']}"
    }}
    """
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.7,
            max_output_tokens=1200,
        )
    )
    return json.loads(response.text)


def word_count(text):
    return len(text.split())


def ensure_script_length(topic, script_data, target_min_seconds=TARGET_MIN_SECONDS,
                          words_per_second=WORDS_PER_SECOND, max_repair_passes=3):
    """
    Verify total narration is long enough to hit the target runtime.
    If not, expand the shortest scenes (in order) and re-check, up to max_repair_passes times.
    """
    target_min_words = int(target_min_seconds * words_per_second)

    for pass_num in range(1, max_repair_passes + 1):
        total_words = sum(word_count(s["narration"]) for s in script_data["scenes"])
        est_seconds = total_words / words_per_second
        print(f"[Length check pass {pass_num}] total_words={total_words} "
              f"(~{est_seconds:.0f}s / target {target_min_seconds}s+)")

        if total_words >= target_min_words:
            print("Script length OK.")
            return script_data

        shortfall_words = target_min_words - total_words
        print(f"Script is short by ~{shortfall_words} words. Expanding shortest scenes...")

        # Expand scenes starting with the shortest, until we've closed the gap or run out of scenes
        scenes_by_length = sorted(script_data["scenes"], key=lambda s: word_count(s["narration"]))
        words_added = 0

        for scene in scenes_by_length:
            if words_added >= shortfall_words:
                break
            current_words = word_count(scene["narration"])
            # push each expanded scene to roughly double its current length, with a sane floor
            min_words_for_scene = max(current_words * 2, 130)
            try:
                expanded = expand_scene(topic, scene, current_words, min_words_for_scene)
                new_words = word_count(expanded["narration"])
                if new_words > current_words:
                    scene["narration"] = expanded["narration"]
                    words_added += (new_words - current_words)
                    print(f"  Scene {scene['scene_number']}: {current_words} -> {new_words} words")
            except Exception as e:
                print(f"  Scene {scene['scene_number']} expansion failed, skipping: {e}")

        if words_added == 0:
            print("No scene could be expanded further this pass; stopping repair loop.")
            break

    total_words = sum(word_count(s["narration"]) for s in script_data["scenes"])
    est_seconds = total_words / words_per_second
    print(f"[Final] total_words={total_words} (~{est_seconds:.0f}s estimated)")
    if est_seconds < target_min_seconds:
        print("WARNING: still under target after repair passes. Proceeding anyway with what we have.")
    return script_data


def _search_pexels(query, headers, per_page=15):
    url = f"https://api.pexels.com/videos/search?query={requests.utils.quote(query)}&per_page={per_page}&orientation=landscape&size=medium"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res.json().get("videos", [])


def _pick_best_video_file(video, min_width=1280):
    """Prefer a landscape HD-ish file over whatever happens to be first in the list."""
    files = video.get("video_files", [])
    hd_candidates = [f for f in files if f.get("width", 0) >= min_width and f.get("width", 0) >= f.get("height", 0)]
    pool = hd_candidates if hd_candidates else files
    if not pool:
        return None
    # pick the largest width available in the pool (better source quality to crop from)
    return max(pool, key=lambda f: f.get("width", 0))


def download_pexels_video(keyword, output_filename, min_scene_seconds=4, fallback_keyword="business finance"):
    """
    Search Pexels for footage matching `keyword`. Filters out clips shorter than the
    scene needs and picks a genuinely landscape/HD file instead of index [0].
    Falls back to a broader finance-generic query rather than silently dropping the scene.
    """
    headers = {"Authorization": PEXELS_KEY}

    for attempt_query in (keyword, fallback_keyword):
        print(f"Searching Pexels for B-roll: '{attempt_query}'")
        try:
            videos = _search_pexels(attempt_query, headers)
        except Exception as e:
            print(f"  Pexels search failed for '{attempt_query}': {e}")
            continue

        # filter out very short clips that would force ugly looping/freezing
        usable = [v for v in videos if v.get("duration", 0) >= min_scene_seconds]
        if not usable:
            usable = videos  # better than nothing if everything is short

        for video in usable:
            best_file = _pick_best_video_file(video)
            if not best_file:
                continue
            print(f"  Selected clip id={video.get('id')} ({best_file.get('width')}x{best_file.get('height')}, "
                  f"{video.get('duration')}s) for query '{attempt_query}'")
            vid_res = requests.get(best_file["link"])
            if vid_res.status_code == 200 and len(vid_res.content) > 0:
                with open(output_filename, 'wb') as f:
                    f.write(vid_res.content)
                return True

        print(f"  No usable clip found for '{attempt_query}'.")

    print(f"  FAILED to find any B-roll for '{keyword}' or fallback - scene will be dropped.")
    return False


def main():
    topic = os.getenv("TOPIC", "The Collapse of Toys R Us")
    print(f"Generating 8-10 minute American documentary for: {topic}")

    script_data = generate_script(topic)
    script_data = ensure_script_length(topic, script_data)

    with open("metadata.txt", "w") as f:
        f.write(f"Title: {script_data['title']}\n")
        f.write(f"Description: {script_data['description']}\n")

    valid_scenes = []

    for scene in script_data["scenes"]:
        sn = scene["scene_number"]
        narration = scene["narration"]
        keyword = scene["broll_keyword"]

        print(f"Generating American voiceover and subtitles for Scene {sn} "
              f"({word_count(narration)} words)...")
        subprocess.run([
            "edge-tts",
            "--voice", "en-US-ChristopherNeural",
            "--rate", "+5%",
            "--text", narration,
            "--write-media", f"audio_{sn}.mp3",
            "--write-subtitles", f"subs_{sn}.vtt"
        ], check=True)

        if not download_pexels_video(keyword, f"video_{sn}.mp4"):
            continue

        print(f"Calculating exact audio duration for Scene {sn}...")
        # edge-tts MP3s are VBR and often lack an accurate header, so ffprobe's
        # format=duration estimate (bitrate * filesize) can be wrong by a second
        # or more - which caused the mid-scene audio cutoffs. Decoding to a PCM
        # WAV first gives ffprobe the real sample count to measure against.
        subprocess.run([
            "ffmpeg", "-y", "-i", f"audio_{sn}.mp3", f"audio_{sn}.wav"
        ], check=True)
        duration = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            f"audio_{sn}.wav"
        ]).decode('utf-8').strip()
        # small safety pad so the very last syllable isn't clipped by rounding
        duration = str(float(duration) + 0.15)

        print(f"Merging Scene {sn}: locking timestamps for long-form looping...")
        subprocess.run([
            "ffmpeg",
            "-stream_loop", "-1",
            "-i", f"video_{sn}.mp4",
            "-i", f"audio_{sn}.wav",
            "-vf", f"fps=30,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,"
                   f"setpts=PTS-STARTPTS,subtitles=subs_{sn}.vtt:force_style='FontName=Arial,FontSize=28,"
                   f"PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2'",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "28",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",
            "-ar", "44100",
            "-video_track_timescale", "90000",
            "-t", str(duration),
            "-y", f"scene_{sn}_final.mp4"
        ], check=True)

        valid_scenes.append(f"file 'scene_{sn}_final.mp4'")

    with open("concat_list.txt", "w") as f:
        f.write("\n".join(valid_scenes))

    print("Stitching final long-form documentary...")
    # NOTE: "-c copy" here was the cause of the mid-video audio cuts. Every scene's
    # AAC audio was encoded independently, and AAC streams carry a few "priming"
    # samples of silence at their start. Stream-copying separately-encoded AAC
    # segments together doesn't smooth that boundary out, so you get an audible
    # click/dropout at every scene transition. Re-encoding at this step (decode
    # then re-encode once, continuously) removes those per-segment boundaries.
    subprocess.run([
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", "concat_list.txt",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-y", "final_documentary.mp4"
    ], check=True)

    # Final sanity check: report actual rendered duration vs target
    try:
        final_duration = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            "final_documentary.mp4"
        ]).decode('utf-8').strip())
        print(f"Final rendered duration: {final_duration:.0f}s "
              f"(target {TARGET_MIN_SECONDS}-{TARGET_MAX_SECONDS}s)")
    except Exception as e:
        print(f"Could not verify final duration: {e}")

    print("Master long-form documentary rendered successfully!")


if __name__ == "__main__":
    main()
