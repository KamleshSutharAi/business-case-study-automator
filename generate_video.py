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

def generate_script(topic):
    prompt = f"""
    You are an elite YouTube documentary producer for a high-RPM American finance channel.
    Write a hyper-engaging, fast-paced 5-scene script about: {topic}.
    
    RULES FOR MAXIMUM RETENTION (US AUDIENCE):
    1. Scene 1 MUST start with a shocking 3-second hook (e.g., a massive dollar amount, a fatal business mistake, or an aggressive question). 
    2. Write in short, punchy, dramatic American English sentences. Use high-stakes storytelling.
    3. Keep each scene's narration extremely brief (under 8 seconds of speech) to force fast visual cuts.
    4. B-roll keywords must be simple, 1-2 words (e.g., "money", "office", "graph", "panic", "crowd").
    
    Return your response strictly as valid JSON matching this format:
    {{
        "title": "Compelling Title",
        "description": "Engaging description with tags",
        "scenes": [
            {{
                "scene_number": 1,
                "narration": "Short punchy hook narration...",
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
        )
    )
    return json.loads(response.text)

def download_pexels_video(keyword, output_filename):
    print(f"Searching Pexels for B-roll: {keyword}")
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=15&orientation=landscape&size=medium"
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    
    data = res.json()
    if not data.get("videos"):
        print(f"No video found for {keyword}, skipping...")
        return False
        
    video_url = data["videos"][0]["video_files"][0]["link"]
    
    print(f"Downloading video to {output_filename}...")
    vid_res = requests.get(video_url)
    with open(output_filename, 'wb') as f:
        f.write(vid_res.content)
    return True

def main():
    topic = os.getenv("TOPIC", "The Collapse of Toys R Us")
    print(f"Generating highly compressed, American-targeted documentary for: {topic}")
    
    script_data = generate_script(topic)
    
    with open("metadata.txt", "w") as f:
        f.write(f"Title: {script_data['title']}\n")
        f.write(f"Description: {script_data['description']}\n")
        
    valid_scenes = []
    
    for scene in script_data["scenes"]:
        sn = scene["scene_number"]
        narration = scene["narration"]
        keyword = scene["broll_keyword"]
        
        print(f"Generating American voiceover and subtitles for Scene {sn}...")
        # Added American Male Voice (Christopher)
        subprocess.run([
            "edge-tts",
            "--voice", "en-US-ChristopherNeural",
            "--text", narration,
            "--write-media", f"audio_{sn}.mp3",
            "--write-subtitles", f"subs_{sn}.vtt"
        ], check=True)
        
        if not download_pexels_video(keyword, f"video_{sn}.mp4"):
            continue
            
        print(f"Calculating exact audio duration for Scene {sn}...")
        duration = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            f"audio_{sn}.mp3"
        ]).decode('utf-8').strip()
            
        print(f"Merging Scene {sn}: locking timestamps and compressing...")
        subprocess.run([
            "ffmpeg",
            "-stream_loop", "-1", 
            "-i", f"video_{sn}.mp4",
            "-i", f"audio_{sn}.mp3",
            "-vf", f"fps=30,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setpts=PTS-STARTPTS,subtitles=subs_{sn}.vtt:force_style='FontName=Arial,FontSize=28,PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=1,Outline=3,Shadow=1,Alignment=2'",
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
        
    print("Stitching final bug-free documentary...")
    subprocess.run([
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", "concat_list.txt",
        "-c", "copy",
        "-y", "final_documentary.mp4"
    ], check=True)
    
    print("Master documentary rendered successfully!")

if __name__ == "__main__":
    main()
