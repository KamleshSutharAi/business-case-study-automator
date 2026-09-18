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
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([item['text'] for item in transcript_list])[:12000]
    except Exception:
        return "High-retention documentary autopsy style with sharp hook and rapid cuts."

def reverse_engineer_and_generate(competitor_transcript, new_topic):
    prompt = f"""
    You are an elite YouTube documentary strategist.
    Write a 100% ORIGINAL 5-scene documentary script about: "{new_topic}".
    Apply the exact pacing and narrative momentum found in top-tier business case studies.
    
    RULES FOR MICRO-CUTS & PREMIUM HUMOR:
    1. Hook-Driven Humor: Scene 1 MUST start with a sarcastic, witty, or shocking hook. 
    2. Write in short, punchy, dramatic American English sentences.
    3. MICRO-CUTS: Provide TWO visual search terms per scene. They must physically match the narration (e.g., "Wall Street panic", "Adam Neumann laughing").
    4. Provide a 2-4 word bold "pop_up_text" for each scene (e.g., "$40B GONE", "THE SCAM").
    
    Return strictly a JSON object:
    {{
        "title": "High-CTR Title",
        "description": "Engaging description",
        "scenes": [
            {{
                "scene_number": 1,
                "narration": "Short, punchy narration line...",
                "visual_source_1": "wikipedia",
                "visual_search_term_1": "Adam Neumann",
                "visual_source_2": "pollinations",
                "visual_search_term_2": "falling stock chart red",
                "pop_up_text": "CRASH TO ZERO"
            }}
        ]
    }}
    """
    
    max_retries = 5
    wait_time = 15
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.7)
            )
            return json.loads(response.text)
        except Exception as e:
            if "503" in str(e) or "UNAVAILABLE" in str(e):
                time.sleep(wait_time)
                wait_time *= 2 
            else:
                raise e
    raise Exception("Failed to generate script due to server overload.")

def fetch_image(source, search_query, duration):
    image_url = None
    if source == "wikipedia":
        api_url = f"https://en.wikipedia.org/w/api.php?action=query&format=json&generator=search&gsrsearch={urllib.parse.quote(search_query)}&gsrlimit=1&prop=pageimages&piprop=original"
        try:
            res = requests.get(api_url, headers={"User-Agent": "YouTubeDocBot/1.0"}).json()
            for _, data in res.get("query", {}).get("pages", {}).items():
                if "original" in data:
                    image_url = data["original"]["source"]
                    break
        except Exception:
            pass

    if not image_url:
        safe_prompt = urllib.parse.quote(f"{search_query}, dark investigative documentary style, cinematic 4k")
        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1920&height=1080&nologo=true&seed={int(float(duration)*100)}"

    try:
        img_data = requests.get(image_url).content
        temp_name = f"temp_{int(time.time()*1000)}.jpg"
        with open(temp_name, "wb") as f:
            f.write(img_data)
        return temp_name
    except Exception:
        return None

def main():
    competitor_url = os.getenv("COMPETITOR_URL", "https://www.youtube.com/watch?v=P3QK-32bxgw")
    new_topic = os.getenv("TOPIC", "The $40 Billion Collapse of WeWork")
    
    script_data = reverse_engineer_and_generate(fetch_competitor_transcript(competitor_url), new_topic)
    
    valid_scenes = []
    
    for scene in script_data["scenes"]:
        sn = scene["scene_number"]
        narration = scene["narration"].replace("\n", " ").replace("\r", " ").strip()
        pop_up = scene.get("pop_up_text", "")
        
        with open(f"narration_{sn}.txt", "w", encoding="utf-8") as f:
            f.write(narration)
            
        subprocess.run([
            "edge-tts", "--voice", "en-US-ChristopherNeural", "-f", f"narration_{sn}.txt",
            "--write-media", f"audio_{sn}.mp3", "--write-subtitles", f"subs_{sn}.vtt"
        ], check=True)
        
        duration = float(subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", f"audio_{sn}.mp3"
        ]).decode('utf-8').strip())
        
        # Micro-cuts: Split duration across 2 images
        half_dur = duration / 2.0
        
        img1 = fetch_image(scene.get("visual_source_1", "pollinations"), scene["visual_search_term_1"], half_dur)
        img2 = fetch_image(scene.get("visual_source_2", "pollinations"), scene["visual_search_term_2"], half_dur)
        
        if not img1 or not img2:
            continue
            
        # Render Micro-cut 1
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", img1,
            "-vf", f"crop=1920:1040:0:0,scale=1920:1080,zoompan=z='min(zoom+0.0012,1.2)':d={int(half_dur*30)}:s=1920x1080:fps=30,eq=contrast=1.15:brightness=-0.04:saturation=0.85,vignette=angle=PI/3.5",
            "-c:v", "libx264", "-t", str(half_dur), "-pix_fmt", "yuv420p", f"clip_{sn}_1.mp4"
        ], check=True)
        
        # Render Micro-cut 2
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", img2,
            "-vf", f"crop=1920:1040:0:0,scale=1920:1080,zoompan=z='min(zoom+0.0012,1.2)':d={int(half_dur*30)}:s=1920x1080:fps=30,eq=contrast=1.15:brightness=-0.04:saturation=0.85,vignette=angle=PI/3.5",
            "-c:v", "libx264", "-t", str(half_dur), "-pix_fmt", "yuv420p", f"clip_{sn}_2.mp4"
        ], check=True)
        
        # Merge cuts 
        with open(f"merge_{sn}.txt", "w") as f:
            f.write(f"file 'clip_{sn}_1.mp4'\nfile 'clip_{sn}_2.mp4'")
            
        subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", f"merge_{sn}.txt", "-c", "copy", f"video_{sn}.mp4"], check=True)
        
        # Final assembly with subtitles and pop-up graphics
        subprocess.run([
            "ffmpeg", "-y", "-i", f"video_{sn}.mp4", "-i", f"audio_{sn}.mp3",
            "-vf", f"fps=30,drawtext=text='{pop_up}':fontcolor=yellow:fontsize=80:x=(w-text_w)/2:y=(h-text_h)/2:borderw=4:bordercolor=black,subtitles=subs_{sn}.vtt:force_style='FontName=Arial,FontSize=28,PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=1,Outline=3,Shadow=2,Alignment=2,MarginL=150,MarginR=150,MarginV=80,WrapStyle=1'",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "128k",
            "-ac", "2", "-ar", "44100", "-video_track_timescale", "90000", "-t", str(duration), f"scene_{sn}_final.mp4"
        ], check=True)
        
        valid_scenes.append(f"file 'scene_{sn}_final.mp4'")
        os.remove(img1)
        os.remove(img2)
        
    with open("concat_list.txt", "w") as f:
        f.write("\n".join(valid_scenes))
        
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", "concat_list.txt", "-c", "copy", "final_documentary.mp4"], check=True)

if __name__ == "__main__":
    main()
