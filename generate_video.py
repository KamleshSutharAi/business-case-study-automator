import os
import json
import urllib.parse
import requests
import subprocess
from google import genai
from google.genai import types

# 1. Fetch Gemini API Key from GitHub Secrets
# Note: Pexels and Pixazo keys are no longer required for this zero-cost AI pipeline.
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_KEY:
    raise ValueError("Missing GEMINI_API_KEY in GitHub Secrets.")

client = genai.Client(api_key=GEMINI_KEY)

def generate_script(topic):
    prompt = f"""
    You are an elite YouTube documentary producer for a high-RPM finance channel.
    Write a fast-paced 5-scene script about: {topic}.
    
    RULES:
    1. Scene 1 MUST start with a shocking 3-second hook.
    2. Write in short, punchy, dramatic sentences.
    3. Keep each scene's narration under 8 seconds.
    4. B-roll keywords must be highly descriptive visual prompts for an AI image generator (e.g., "abandoned wall street trading floor in panic", "close up of hands counting money").
    
    Return your response strictly as valid JSON matching this format:
    {{
        "title": "Compelling Title",
        "description": "Engaging description with tags",
        "scenes": [
            {{
                "scene_number": 1,
                "narration": "Short punchy phrase.",
                "broll_keyword": "visual description"
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

def generate_free_ai_scene(prompt, output_mp4, duration):
    print(f"Generating free AI image for: {prompt}")
    
    # Generate Free AI Image via Pollinations (No API Key Required)
    safe_prompt = urllib.parse.quote(prompt + ", highly detailed cinematic documentary style, 4k resolution")
    image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1920&height=1080&nologo=true"
    
    image_filename = "temp_scene.jpg"
    response = requests.get(image_url)
    if response.status_code != 200:
        print("Failed to generate AI image. Falling back to default.")
        safe_prompt = urllib.parse.quote("cinematic dark business office background")
        image_url = f"https://image.pollinations.ai/prompt/{safe_prompt}?width=1920&height=1080&nologo=true"
        response = requests.get(image_url)
        
    with open(image_filename, 'wb') as f:
        f.write(response.content)
        
    print(f"Animating AI image into a {duration}s video clip using FFmpeg zoompan...")
    
    # Animate with FFmpeg Zoom & Pan (Ken Burns effect)
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
    topic = os.getenv("TOPIC", "The Collapse of Toys R Us")
    print(f"Generating premium AI documentary for: {topic}")
    
    script_data = generate_script(topic)
    
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
        
        # Calculate precise audio duration
        duration = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "default=noprint_wrappers=1:nokey=1",
            f"audio_{sn}.mp3"
        ]).decode('utf-8').strip()
        
        # Generate and animate custom AI visual
        if not generate_free_ai_scene(keyword, f"video_{sn}.mp4", duration):
            continue
            
        print(f"Merging Scene {sn}: locking subtitles with smart word-wrap and side margins...")
        
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
        
    print("Stitching final premium AI documentary...")
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "concat_list.txt",
        "-c", "copy",
        "final_documentary.mp4"
    ], check=True)
    
    print("Master AI documentary rendered successfully!")

if __name__ == "__main__":
    main()
