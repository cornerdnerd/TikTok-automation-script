import os
import json
import random
import librosa
import numpy as np
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip
from datetime import datetime

from tiktok_uploader import TikTokUploader
uploader = TikTokUploader(cookies_file="tiktok_cookies.json")



# ===== CONFIGURATION VARIABLES =====
CLIPS_GOON_FOLDER = "clips/goon"      # Folder for intro clips (shown only once)
CLIPS_EDIT_FOLDER = "clips/edit"      # Folder for main clips
AUDIO_FOLDER = "audios"               # Folder containing audio files
OUTPUT_FOLDER = "output"              # Where to save the final video
MIN_INTRO_DURATION = 2              # Minimum duration for intro clip in seconds (goon clip)
LOOP = False                          # Set to True to loop the script
TIKTOK_UPLOAD = True                # Set to True to auto upload to TikTok
DESCRIPTION = ["dxdcrew.onrender.com", "DXDCREW ON TOP"]  # Description for TikTok upload
# ===================================

# Prompt to get cookies
if not os.path.exists("tiktok_cookies.json") and TIKTOK_UPLOAD:
    TikTokUploader.save_cookies()

#create paths if they dont exist
if not os.path.exists(CLIPS_GOON_FOLDER):
    os.makedirs(CLIPS_GOON_FOLDER)
if not os.path.exists(CLIPS_EDIT_FOLDER):
    os.makedirs(CLIPS_EDIT_FOLDER)
if not os.path.exists(AUDIO_FOLDER):
    os.makedirs(AUDIO_FOLDER)
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

# Desired final size
final_size = (1080, 1920)  # TikTok format (9:16)

def prepare_clip(clip):
    # Resize proportionally to fit height
    clip = clip.resize(height=final_size[1])
    if clip.w < final_size[0]:
        clip = clip.resize(width=final_size[0])
        
    # Pad it to final resolution (centered with black bars if needed)
    return clip.on_color(
        size=final_size,
        color=(0, 0, 0),
        pos=("center", "center")
    )



def detect_beats(audio_file, config_file=None):
    """Detect beats from an audio file or load them from a config file."""
    labeled_beats = {}
    
    if config_file and os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        if 'labeled_beats' in config:
            labeled_beats = config['labeled_beats']
            all_beats = []
            for label, times in labeled_beats.items():
                all_beats.extend(times)
            return sorted(all_beats), labeled_beats
        elif 'beats' in config:
            return config['beats'], labeled_beats
    
    print("Detecting beats from audio file...")
    y, sr = librosa.load(audio_file)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr)
    
    try:
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        mean_strength = np.mean(onset_env)
        strong_onsets_frames = librosa.util.peak_pick(
            onset_env, 
            pre_max=30, post_max=30, 
            pre_avg=30, post_avg=30, 
            delta=mean_strength*0.8, wait=25
        )
        strong_onsets = librosa.frames_to_time(strong_onsets_frames, sr=sr)
        if len(strong_onsets) > 0:
            labeled_beats['drop'] = list(map(float, strong_onsets))
            print(f"Detected {len(strong_onsets)} potential beat drops")
    except Exception as e:
        print(f"Could not detect beat drops: {str(e)}")
    
    return list(map(float, beat_times)), labeled_beats

def get_video_files_from_folder(folder_path):
    """Get all video files from the specified folder."""
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
        print(f"Created folder: {folder_path}")
        return []
    
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
    video_files = []
    for file in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file)
        if os.path.isfile(file_path) and any(file.lower().endswith(ext) for ext in video_extensions):
            video_files.append(file_path)
    
    video_files.sort()
    return video_files

def get_random_audio_file():
    """Get a random audio file from the audio folder."""
    if not os.path.exists(AUDIO_FOLDER):
        os.makedirs(AUDIO_FOLDER)
        print(f"Created folder: {AUDIO_FOLDER}")
        return None
    
    audio_extensions = ['.mp3', '.wav', '.ogg', '.m4a', '.flac']
    audio_files = []
    for file in os.listdir(AUDIO_FOLDER):
        file_path = os.path.join(AUDIO_FOLDER, file)
        if os.path.isfile(file_path) and any(file.lower().endswith(ext) for ext in audio_extensions):
            audio_files.append(file_path)
    
    return random.choice(audio_files) if audio_files else None

def create_beat_synchronized_video(audio_file=None, config_file=None):
    """Create a beat-synchronized video with proper intro clip timing."""
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(OUTPUT_FOLDER, f"beat_synced_{timestamp}.mp4")
    
    if audio_file is None:
        audio_file = get_random_audio_file()
        if audio_file is None:
            raise FileNotFoundError(f"No audio files found in {AUDIO_FOLDER} folder")
        print(f"Using random audio file: {audio_file}")
    
    if not os.path.exists(audio_file):
        raise FileNotFoundError(f"Audio file not found: {audio_file}")
    
    # Get clips
    goon_clips = get_video_files_from_folder(CLIPS_GOON_FOLDER)
    zeta_clips = get_video_files_from_folder(CLIPS_EDIT_FOLDER)
    
    if not goon_clips and not zeta_clips:
        raise ValueError(f"No video files found in either {CLIPS_GOON_FOLDER} or {CLIPS_EDIT_FOLDER} folders.")
    
    # Select one random goon clip for intro (will be removed from pool)
    intro_clip_path = random.choice(goon_clips) if goon_clips else random.choice(zeta_clips)
    remaining_clips = zeta_clips  # All zeta clips are available for main segments
    
    # Load beats
    beats, labeled_beats = detect_beats(audio_file, config_file)
    print(f"Detected {len(beats)} beats in the audio file.")
    
    if not beats:
        raise ValueError("No beats detected or provided.")
    
    # Find first beat after MIN_INTRO_DURATION
    next_beat_after_intro = next((b for b in beats if b >= MIN_INTRO_DURATION), None)

    if next_beat_after_intro is None:
        raise ValueError("No beat found after MIN_INTRO_DURATION")

    intro_end_time = next_beat_after_intro
    print(f"Intro will end at next beat: {intro_end_time:.2f}s")

    # Load intro clip
    try:
        intro_clip = VideoFileClip(intro_clip_path)
        print(f"Loaded intro clip: {intro_clip_path} (duration: {intro_clip.duration:.2f}s)")
    except Exception as e:
        print(f"Error loading intro clip: {str(e)}")
        raise
    
    # Create segments
    segments = []


    # 1. Intro segment (from start to beat drop) with minimum duration
    try:
        # Find the first beat that satisfies the minimum duration
        # Find the first beat after MIN_INTRO_DURATION
        valid_intro_beats = [b for b in beats if b >= MIN_INTRO_DURATION]

        if not valid_intro_beats:
            intro_end_time = max(MIN_INTRO_DURATION, next_beat_after_intro)
        else:
            intro_end_time = valid_intro_beats[0]

        
        # Ensure we don't exceed the beat drop time
        intro_end_time = min(intro_end_time, next_beat_after_intro)
        
        # Create intro segment
        if intro_end_time > intro_clip.duration:
            num_loops = int(np.ceil(intro_end_time / intro_clip.duration))
            intro_segment = concatenate_videoclips([intro_clip] * num_loops)
            intro_segment = intro_segment.subclip(0, intro_end_time)
        else:
            intro_segment = intro_clip.subclip(0, intro_end_time)
        
        segments.append(prepare_clip(intro_segment))
        print(f"Created intro segment (0 to {intro_end_time:.2f}s)")
    except Exception as e:
        print(f"Error creating intro segment: {str(e)}")
        raise
    

    
    # Load audio
    audio = AudioFileClip(audio_file)
    audio_duration = audio.duration
    print(f"Audio duration: {audio_duration:.2f} seconds")
    

    
    # Load remaining clips
    clips = []
    for clip_path in remaining_clips:
        try:
            clip = VideoFileClip(clip_path)
            clips.append(clip)
            print(f"Loaded clip: {clip_path} (duration: {clip.duration:.2f}s)")
        except Exception as e:
            print(f"Warning: Could not load {clip_path}: {str(e)}")
    
    if not clips:
        print("Warning: No additional clips loaded, will reuse intro clip if needed")
        clips.append(intro_clip)
    
    # Decide the order: forward or reverse
    clip_sequence = clips if random.choice([True, False]) else list(reversed(clips))


    

    
    # 2. Post-drop segments (normal beat synchronization)
    # Use beats AFTER the actual intro_end_time (not beat drop)
    beats_after_intro = [b for b in beats if b > intro_end_time]

    print(f"Found {len(beats_after_intro)} beats after intro")
    
    clip_sequence_len = len(clip_sequence)
    seq_index = 0
    
    for i in range(len(beats_after_intro) - 1):
        try:
            start_time = float(beats_after_intro[i])
            end_time = float(beats_after_intro[i + 1])
            duration = end_time - start_time

            current_clip = clip_sequence[seq_index % clip_sequence_len]
            seq_index += 1

            if duration > current_clip.duration:
                num_loops = int(np.ceil(duration / current_clip.duration))
                segment = concatenate_videoclips([current_clip] * num_loops)
                segment = segment.subclip(0, duration)
            else:
                segment = current_clip.subclip(0, duration)

            segments.append(prepare_clip(segment))
            print(f"Created segment {len(segments)}: {start_time:.2f}s to {end_time:.2f}s (duration: {duration:.2f}s)")
        except Exception as e:
            print(f"Error creating segment: {str(e)}")
            continue
    
    # Final segment if needed
    if beats_after_intro and beats_after_intro[-1] < audio_duration:
        try:
            duration = audio_duration - beats_after_intro[-1]

            current_clip = clip_sequence[seq_index % clip_sequence_len]
            seq_index += 1
            
            if duration > current_clip.duration:
                num_loops = int(np.ceil(duration / current_clip.duration))
                segment = concatenate_videoclips([current_clip] * num_loops)
                segment = segment.subclip(0, duration)
            else:
                segment = current_clip.subclip(0, duration)
            
            segments.append(prepare_clip(segment))
            print(f"Created final segment: {beats_after_intro[-1]:.2f}s to end (duration: {duration:.2f}s)")
        except Exception as e:
            print(f"Error creating final segment: {str(e)}")
    
    if not segments:
        raise ValueError("Failed to create any valid video segments.")
    
    print(f"Created {len(segments)} video segments. Concatenating...")
    
    try:
        
        final_video = concatenate_videoclips(segments, method="compose")
        max_audio_duration = min(audio.duration, final_video.duration)
        final_video = final_video.set_audio(audio.subclip(0, max_audio_duration))

        
        print("Rendering final video...")
        final_video.write_videofile(
            output_file, 
            codec='libx264', 
            audio_codec='aac',
            logger=None
        )
        
        audio.close()
        intro_clip.close()
        for clip in clips:
            clip.close()
        final_video.close()
        
        print(f"Video successfully created: {output_file}")
        return output_file
    
    except Exception as e:
        print(f"Error during video rendering: {str(e)}")
        try:
            audio.close()
            intro_clip.close()
            for clip in clips:
                clip.close()
        except:
            pass
        raise

def main():
    """Main function to create a beat-synchronized video."""
    try:
        # Check folders
        for folder in [CLIPS_GOON_FOLDER, CLIPS_EDIT_FOLDER, AUDIO_FOLDER, OUTPUT_FOLDER]:
            os.makedirs(folder, exist_ok=True)
        
        # Check for clips
        goon_clips = get_video_files_from_folder(CLIPS_GOON_FOLDER)
        zeta_clips = get_video_files_from_folder(CLIPS_EDIT_FOLDER)
        
        if not goon_clips and not zeta_clips:
            print(f"No video files found in either {CLIPS_GOON_FOLDER} or {CLIPS_EDIT_FOLDER} folders.")
            return
        
        # Check for audio files
        audio_files = [f for f in os.listdir(AUDIO_FOLDER) if f.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac'))]
        if not audio_files:
            print(f"No audio files found in {AUDIO_FOLDER} folder.")
            return
        
        

        # Create video
        output_file = create_beat_synchronized_video()
        print(f"\nFinal video saved as: {output_file}")
        if TIKTOK_UPLOAD:
            print("Uploading to TikTok...")
            # Upload a single video
            uploader.upload_video(
                video_path=output_file,
                description=DESCRIPTION[random.randint(0, len(DESCRIPTION)-1)],
                hashtags=["viral", "fyp", "trending"]
            )
        
    except Exception as e:
        print(f"Error: {str(e)}")
        print("\nUsage instructions:")
        print(f"1. Place audio files in the '{AUDIO_FOLDER}' folder")
        print(f"2. Place intro video clips in '{CLIPS_GOON_FOLDER}' folder")
        print(f"3. Place main video clips in '{CLIPS_EDIT_FOLDER}' folder")
        print("4. Run this script to create a beat-synchronized video")

if __name__ == "__main__":
    if LOOP:
        while True:
            main()
    else:
        main()
