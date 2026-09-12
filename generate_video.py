import os
import re
import json
import requests
import asyncio
import edge_tts
import subprocess
from google import genai
from google.genai import types

# 1. Fetch API Keys from GitHub Secrets
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
PEXELS_KEY = os.getenv("PEXELS_API_KEY")

if not GEMINI_KEY or not PEXELS_KEY:
    raise ValueError("Missing GEMINI_API_KEY or PEXELS_API_KEY in environment variables.")

# 2. Configure Gemini Client
client = genai.Client(api_key=GEMINI_KEY)

TOPIC = os.getenv("VIDEO_TOPIC", "The Rise and Fall of Blockbuster")

def generate_script(topic):
    print(f"Generating documentary script for: {topic}...")
    prompt = f"""
    You are an elite investigative business documentarian for the YouTube channel 'The Monopoly Files'.
    Write a 3-scene documentary script about: "{topic}".
    
    Return your response strictly as valid JSON with no extra commentary or markdown backticks:
    {{
      "title": "Compelling Click-Worthy Title",
      "description": "Engaging description with relevant hashtags.",
      "scenes": [
        {{
          "scene_number": 1,
          "narration": "Full narration text for this segment (around 40-50 words).",
          "broll_keyword": "simple search term for stock video (e.g. office building, warehouse, money)"
        }},
        {{
          "scene_number": 2,
          "narration": "Full narration text for the turning point or crisis (around 40-50 words).",
          "broll_keyword": "search term for stock video (e.g. stock market crash, closed store)"
        }},
        {{
          "scene_number": 3,
          "narration": "Full narration text for the takeaway or conclusion (around 40-50 words).",
          "broll_keyword": "search term for stock video (e.g. handshake, technology, empty street)"
        }}
      ]
    }}
    """
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return json.loads(response.text)

def download_pexels_video(keyword, output_filename):
    print(f"Searching Pexels for B-roll: {keyword}...")
    headers = {"Authorization": PEXELS_KEY}
    url = f"https://api.pexels.com/videos/search?query={keyword}&per_page=1&orientation=landscape"
    res = requests.get(url, headers=headers).json()
    
    video_files = res.get("videos", [{}])[0].get("video_files", [])
    selected_video = None
    for vf in video_files:
        if vf.get("width") == 1920 or vf.get("height") == 1080:
            selected_video = vf.get("link")
            break
    if not selected_video and video_files:
        selected_video = video_files[0].get("link")
        
    if not selected_video:
        raise Exception(f"No video found on Pexels for keyword: {keyword}")

    video_data = requests.get(selected_video).content
    with open(output_filename, "wb") as f:
        f.write(video_data)
    print(f"Downloaded: {output_filename}")

async def create_voiceover(text, output_audio):
    print(f"Synthesizing voiceover -> {output_audio}...")
    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
    await communicate.save(output_audio)

def get_media_duration(file_path):
    cmd = [
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return float(result.stdout)

def assemble_scene(video_file, audio_file, output_scene_file):
    audio_dur = get_media_duration(audio_file)
    print(f"Assembling scene: {output_scene_file} (Duration: {audio_dur:.2f}s)...")
    
    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", video_file,
        "-i", audio_file,
        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080",
        "-t", str(audio_dur),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", output_scene_file
    ]
    subprocess.run(cmd, check=True)

def concatenate_scenes(scene_files, final_output="final_documentary.mp4"):
    print("Stitching all scenes into finished video...")
    with open("concat_list.txt", "w") as f:
        for sf in scene_files:
            f.write(f"file '{sf}'\n")
            
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", "concat_list.txt",
        "-c", "copy", final_output
    ]
    subprocess.run(cmd, check=True)
    print(f"Video assembly complete: {final_output}")

async def main():
    os.makedirs("workspace", exist_ok=True)
    data = generate_script(TOPIC)
    print(f"\nDocumentary Title: {data['title']}\n")
    
    scene_outputs = []
    for scene in data["scenes"]:
        num = scene["scene_number"]
        v_file = f"workspace/broll_{num}.mp4"
        a_file = f"workspace/audio_{num}.mp3"
        s_file = f"workspace/scene_{num}.mp4"
        
        download_pexels_video(scene["broll_keyword"], v_file)
        await create_voiceover(scene["narration"], a_file)
        assemble_scene(v_file, a_file, s_file)
        scene_outputs.append(s_file)
        
    concatenate_scenes(scene_outputs, "final_documentary.mp4")

if __name__ == "__main__":
    asyncio.run(main())
