import os
import re
import json
import urllib.parse
import requests
import subprocess
from google import genai
from google.genai import types
from youtube_transcript_api import YouTubeTranscriptApi

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_KEY:
    raise ValueError("Missing GEMINI_API_KEY in GitHub Secrets.")

client = genai.Client(api_key=GEMINI_KEY)

def extract_video_id(url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
    return match.group(1) if match else url

def fetch_competitor_transcript(video_url):
    video_id = extract_video_id(video_url)
    print(f"Extracting transcript for video ID: {video_id}...")
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([item['text'] for item in transcript_list])
        print("Transcript successfully extracted.")
        return transcript_text[:12000]
    except Exception as e:
        print(f"Could not extract transcript ({e}). Falling back to general analysis.")
        return "High-retention documentary autopsy style with sharp hook and rapid cuts."

def reverse_engineer_and_generate(competitor_transcript, new_topic):
    print("Reverse-engineering formula and writing new script with Gemini...")
    prompt = f"""
    You are an elite YouTube documentary strategist.
    
    1. Analyze this viral competitor transcript:
    \"\"\"{competitor_transcript}\"\"\"
    
    2. Deconstruct their retention formula:
       - Hook intensity (shock stat, mystery, or existential threat)
       - Narration cadence (sentence length, dramatic tone)
       - Structural progression (Hook -> Escalation -> Turning Point -> Fallout)
    
    3. Write a 100% ORIGINAL 5-scene documentary script about: "{new_topic}".
       Apply their exact structural pacing, hook style, and narrative momentum.
    
    Return strictly a JSON object:
    {{
        "title": "High-CTR Title",
        "description": "Engaging description with tags",
        "scenes": [
            {{
                "scene_number": 1,
                "narration": "Short, punchy narration line...",
                "broll_keyword": "descriptive visual prompt for AI image generator"
            }}
        ]
    }}
    """
    
    response = client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.7,
        )
    )
    return json.loads(response.text)

def generate_free_ai_scene(prompt, output_mp4, duration):
    print(f"Generating AI visual for: {prompt}")
    safe_prompt = urllib.parse.quote(prompt + ", cinematic documentary style, 4k resolution")
    image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1920&height=1080&nologo=true"
    
    image_filename = "temp_scene.jpg"
    response = requests.get(image_url)
    if response.status_code != 200:
        fallback = urllib.parse.quote("dark corporate finance boardroom background")
        response = requests.get(f"https://image.pollinations.ai/prompt/{fallback}?width=1920&height=1080&nologo=true")
        
    with open(image_filename, 'wb') as f:
        f.write(response.content)
        
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_filename,
        "-vf", f"zoompan=z='min(zoom+0.001,1.15)':d={int(float(duration)*30)}:s=1920x1080:fps=30",
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        output_mp4
    ], check=True)
    
    if os.path.exists(image_filename):
        os.remove(image_filename)
    return True

def main():
    competitor_url = os.getenv("COMPETITOR_URL", "https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    new_topic = os.getenv("TOPIC", "The Collapse of Toys R Us")
    
    transcript = fetch_competitor_transcript(competitor_url)
    script_data = reverse_engineer_and_generate(transcript, new_topic)
    
    with open("metadata.txt", "w") as f:
        f.write(f"Title: {script_data['title']}\n")
        f.write(f"Description: {script_data['description']}\n")
        
    valid_scenes = []
    
    for scene in script_data["scenes"]:
        sn = scene["scene_number"]
        narration = scene["narration"]
        keyword = scene["broll_keyword"]
        
        print(f"Generating voiceover and subtitles for Scene {sn}...")
        subprocess.run([
            "edge-tts",
            "--voice", "en-US-ChristopherNeural",
            "--text", narration,
            "--write-media", f"audio_{sn}.mp3",
            "--write-subtitles", f"subs_{sn}.vtt"
        ], check=True)
        
        duration = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            f"audio_{sn}.mp3"
        ]).decode('utf-8').strip()
        
        if not generate_free_ai_scene(keyword, f"video_{sn}.mp4", duration):
            continue
            
        print(f"Merging Scene {sn}...")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", f"video_{sn}.mp4",
            "-i", f"audio_{sn}.mp3",
            "-vf", f"subtitles=subs_{sn}.vtt:force_style='FontName=Arial,FontSize=28,PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=1,Outline=3,Shadow=2,Alignment=2,MarginL=150,MarginR=150,MarginV=60,WrapStyle=1'",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "28",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2",
            "-ar", "44100",
            f"scene_{sn}_final.mp4"
        ], check=True)
        
        valid_scenes.append(f"file 'scene_{sn}_final.mp4'")
        
    with open("concat_list.txt", "w") as f:
        f.write("\n".join(valid_scenes))
        
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "concat_list.txt",
        "-c", "copy",
        "final_documentary.mp4"
    ], check=True)
    
    print("Done! final_documentary.mp4 is ready.")

if __name__ == "__main__":
    main()
