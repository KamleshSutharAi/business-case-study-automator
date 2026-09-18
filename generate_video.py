import os
import re
import json
import urllib.parse
import requests
import subprocess
import time
from google import genai
from google.genai import types
from youtube_transcript_api import YouTubeTranscriptApi

GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_KEY:
    raise ValueError("Missing GEMINI_API_KEY in GitHub Secrets.")

client = genai.Client(api_key=GEMINI_KEY)

def fetch_competitor_transcript(video_url):
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", video_url)
    video_id = match.group(1) if match else video_url
    print(f"Extracting transcript for video ID: {video_id}...")
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript_text = " ".join([item['text'] for item in transcript_list])
        return transcript_text[:12000]
    except Exception as e:
        print(f"Transcript extraction failed ({e}). Using general fallback.")
        return "High-retention documentary autopsy style with sharp hook and rapid cuts."

def reverse_engineer_and_generate(competitor_transcript, new_topic):
    print(f"Reverse-engineering formula and writing new script for: {new_topic}...")
    prompt = f"""
    You are an elite YouTube documentary strategist.
    
    1. Analyze this viral competitor transcript:
    \"\"\"{competitor_transcript}\"\"\"
    
    2. Deconstruct their retention formula (Hook intensity, sentence length, structural progression).
    
    3. Write a 100% ORIGINAL 5-scene documentary script about: "{new_topic}".
       Apply their exact structural pacing, hook style, and narrative momentum.
       
    RULES FOR VISUALS & PACING:
    - WRITE IN EXTREMELY SHORT PHRASES. Maximum 5 to 7 words per sentence.
    - Keep each scene's total narration under 8 seconds.
    - VISUAL VARIETY IS MANDATORY. Alternate between showing Real Historical Figures, Financial Data, and Cinematic B-Roll.
    
    Return strictly a JSON object matching this format:
    {{
        "title": "High-CTR Title",
        "description": "Engaging description with tags",
        "scenes": [
            {{
                "scene_number": 1,
                "narration": "Short, punchy narration line...",
                "visual_source": "wikipedia",
                "visual_search_term": "Adam Neumann"
            }}
        ]
    }}
    Note: Set 'visual_source' to 'wikipedia' ONLY for specific famous people, companies, or logos (e.g., 'Adam Neumann', 'Enron Logo'). Set to 'pollinations' for abstract concepts (e.g., 'financial stock chart crashing red', 'dark empty conference room').
    """
    
    max_retries = 5
    wait_time = 15
    
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7,
                )
            )
            return json.loads(response.text)
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                print(f"Gemini server overloaded (503). Retrying in {wait_time} seconds... (Attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
                wait_time *= 2 
            else:
                raise e
                
    raise Exception("Failed to generate script after multiple retries due to server overload.")

def create_magnates_style_scene(source, search_query, output_mp4, duration):
    print(f"Fetching visual for: {search_query} (Source: {source})...")
    
    image_url = None
    
    # 1. Attempt to fetch real historical press photo from Wikipedia API
    if source == "wikipedia":
        api_url = f"https://en.wikipedia.org/w/api.php?action=query&format=json&generator=search&gsrsearch={urllib.parse.quote(search_query)}&gsrlimit=1&prop=pageimages&piprop=original"
        headers = {"User-Agent": "YouTubeDocBot/1.0"}
        try:
            res = requests.get(api_url, headers=headers).json()
            pages = res.get("query", {}).get("pages", {})
            for page_id, data in pages.items():
                if "original" in data:
                    image_url = data["original"]["source"]
                    print(f"Successfully located Wikipedia Archival Photo for: {search_query}")
                    break
        except Exception as e:
            print(f"Wikipedia search failed: {e}")

    # 2. Fallback to AI generation with unique seed to prevent caching
    if not image_url:
        safe_prompt = urllib.parse.quote(f"{search_query}, dark investigative documentary style, cinematic 4k")
        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1920&height=1080&nologo=true&seed={int(float(duration)*100)}"

    try:
        img_data = requests.get(image_url).content
        with open("archival_temp.jpg", "wb") as f:
            f.write(img_data)
    except Exception:
        safe_prompt = urllib.parse.quote(f"dark corporate finance boardroom background")
        img_data = requests.get(f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1920&height=1080&nologo=true").content
        with open("archival_temp.jpg", "wb") as f:
            f.write(img_data)
        
    print(f"Applying crop (Watermark removal), dark grade, and 2.5D zoom (Duration: {duration}s)...")
    
    # 3. Crop bottom 40px to eradicate Pollinations watermark, scale to 1080p, and apply Ken Burns
    subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", "archival_temp.jpg",
        "-vf", f"crop=1920:1040:0:0,scale=1920:1080,zoompan=z='min(zoom+0.0012,1.2)':d={int(float(duration)*30)}:s=1920x1080:fps=30,eq=contrast=1.15:brightness=-0.04:saturation=0.85,vignette=angle=PI/3.5",
        "-c:v", "libx264",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        output_mp4
    ], check=True)
    
    if os.path.exists("archival_temp.jpg"):
        os.remove("archival_temp.jpg")
    return True

def main():
    competitor_url = os.getenv("COMPETITOR_URL", "https://www.youtube.com/watch?v=P3QK-32bxgw")
    new_topic = os.getenv("TOPIC", "The $40 Billion Collapse of WeWork")
    
    transcript = fetch_competitor_transcript(competitor_url)
    script_data = reverse_engineer_and_generate(transcript, new_topic)
    
    with open("metadata.txt", "w", encoding="utf-8") as f:
        f.write(f"Title: {script_data['title']}\n")
        f.write(f"Description: {script_data['description']}\n")
        
    valid_scenes = []
    
    for scene in script_data["scenes"]:
        sn = scene["scene_number"]
        narration = scene["narration"]
        source = scene.get("visual_source", "pollinations")
        keyword = scene["visual_search_term"]
        
        text_file = f"narration_{sn}.txt"
        with open(text_file, "w", encoding="utf-8") as f:
            f.write(narration)
            
        print(f"Generating voiceover and subtitles for Scene {sn}...")
        subprocess.run([
            "edge-tts",
            "--voice", "en-US-ChristopherNeural",
            "-f", text_file,
            "--write-media", f"audio_{sn}.mp3",
            "--write-subtitles", f"subs_{sn}.vtt"
        ], check=True)
        
        duration = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            f"audio_{sn}.mp3"
        ]).decode('utf-8').strip()
        
        create_magnates_style_scene(source, keyword, f"video_{sn}.mp4", duration)
            
        print(f"Merging Scene {sn}: locking 30fps and 44.1kHz audio with custom captions...")
        subprocess.run([
            "ffmpeg", "-y",
            "-i", f"video_{sn}.mp4",
            "-i", f"audio_{sn}.mp3",
            "-vf", f"fps=30,scale=1920:1080,setpts=PTS-STARTPTS,subtitles=subs_{sn}.vtt:force_style='FontName=Arial,FontSize=28,PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=1,Outline=3,Shadow=2,Alignment=2,MarginL=150,MarginR=150,MarginV=60,WrapStyle=1'",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "28",
            "-r", "30", 
            "-c:a", "aac",
            "-b:a", "128k",
            "-ac", "2", 
            "-ar", "44100", 
            "-video_track_timescale", "90000",
            "-t", str(duration), 
            f"scene_{sn}_final.mp4"
        ], check=True)
        
        valid_scenes.append(f"file 'scene_{sn}_final.mp4'")
        
    with open("concat_list.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(valid_scenes))
        
    print("Stitching final Master documentary...")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "concat_list.txt",
        "-c", "copy",
        "final_documentary.mp4"
    ], check=True)
    
    print("Master documentary rendered successfully!")

if __name__ == "__main__":
    main()
