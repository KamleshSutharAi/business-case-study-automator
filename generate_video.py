import os
import re
import json
import requests
import subprocess
from google import genai
from google.genai import types

# 1. Fetch API Keys from GitHub Secrets
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")

if not GEMINI_KEY or not PEXELS_KEY:
    raise ValueError("Missing API keys. Check GitHub Secrets.")

client = genai.Client(api_key=GEMINI_KEY)

def generate_script(topic):
    prompt = f"""
    You are an elite investigative business documentarian.
    Write a 3-scene documentary script about: {topic}

    Return your response strictly as valid JSON matching this format:
    {{
        "title": "Compelling Title",
        "description": "Engaging description",
        "scenes": [
            {{
                "scene_number": 1,
                "narration": "Full narration text...",
                "broll_keyword": "simple search term for stock footage"
            }}
        ]
    }}
    """
    
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
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
    print(f"Generating documentary for: {topic}")
    
    script_data = generate_script(topic)
    
    # Save script and metadata
    with open("metadata.txt", "w") as f:
        f.write(f"Title: {script_data['title']}\n")
        f.write(f"Description: {script_data['description']}\n")
        
    valid_scenes = []
    
    for scene in script_data["scenes"]:
        sn = scene["scene_number"]
        narration = scene["narration"]
        keyword = scene["broll_keyword"]
        
        # Step A: Generate Audio and Synchronized Subtitles
        print(f"Generating audio and subtitles for Scene {sn}...")
        subprocess.run([
            "edge-tts",
            "--text", narration,
            "--write-media", f"audio_{sn}.mp3",
            "--write-subtitles", f"subs_{sn}.vtt"
        ], check=True)
        
        # Step B: Download B-roll
        if not download_pexels_video(keyword, f"video_{sn}.mp4"):
            continue
            
        # Step C: Merge Video, Audio, and Burn High-Contrast Subtitles
        print(f"Merging Scene {sn} with subtitles and locked framerate...")
        subprocess.run([
            "ffmpeg",
            "-stream_loop", "-1", 
            "-i", f"video_{sn}.mp4",
            "-i", f"audio_{sn}.mp3",
            "-vf", f"fps=30,subtitles=subs_{sn}.vtt:force_style='FontSize=24,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=1,Outline=2,Alignment=2'",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest", 
            "-y", f"scene_{sn}_final.mp4"
        ], check=True)
        
        valid_scenes.append(f"file 'scene_{sn}_final.mp4'")
        
    # Step D: Final Assembly of All Scenes
    with open("concat_list.txt", "w") as f:
        f.write("\n".join(valid_scenes))
        
    print("Stitching final documentary...")
    subprocess.run([
        "ffmpeg",
        "-f", "concat",
        "-safe", "0",
        "-i", "concat_list.txt",
        "-c", "copy",
        "-y", "final_documentary.mp4"
    ], check=True)
    
    print("Documentary rendered successfully!")

if __name__ == "__main__":
    main()
